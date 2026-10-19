"""Inventory ledger operations.

Rules enforced here (and backed by DB check constraints):
  * every change to a balance writes an append-only InventoryTransaction;
  * balances are locked with SELECT ... FOR UPDATE before they are changed;
  * on_hand >= 0, reserved >= 0 and reserved <= on_hand at all times;
  * available = on_hand - reserved, and reservations never exceed available.

Lock ordering (to avoid deadlocks): order -> job/delivery -> balances (ascending id).
Callers own the transaction: these functions never commit.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Material,
    Product,
    ProductionJob,
    Reservation,
    Supplier,
    User,
    Warehouse,
)
from app.models.enums import ItemType, JobStatus, ReservationStatus, TxnType
from app.schemas.inventory import AdjustmentIn, ReceiptIn
from app.services import audit
from app.services.common import get_or_404, qty

ZERO = Decimal("0")


# --------------------------------------------------------------------------- balances


def lock_balance(
    db: Session,
    warehouse_id: int,
    *,
    material_id: int | None = None,
    product_id: int | None = None,
    create: bool = False,
) -> InventoryBalance:
    """Return the balance row for (item, warehouse), locked FOR UPDATE; optionally create it."""
    if (material_id is None) == (product_id is None):
        raise ValueError("Exactly one of material_id / product_id is required")
    col = InventoryBalance.material_id if material_id is not None else InventoryBalance.product_id
    item_id = material_id if material_id is not None else product_id
    if create:
        stmt = pg_insert(InventoryBalance).values(
            item_type=ItemType.MATERIAL if material_id is not None else ItemType.PRODUCT,
            material_id=material_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            on_hand=0,
            reserved=0,
        )
        where_col = "material_id" if material_id is not None else "product_id"
        db.execute(
            stmt.on_conflict_do_nothing(index_elements=[where_col, "warehouse_id"], index_where=text(f"{where_col} IS NOT NULL"))
        )
    bal = (
        db.execute(
            select(InventoryBalance)
            .where(col == item_id, InventoryBalance.warehouse_id == warehouse_id)
            .with_for_update(of=InventoryBalance)
            .execution_options(populate_existing=True)
        )
        .unique()
        .scalar_one_or_none()
    )
    if bal is None:
        raise BusinessRuleError("No stock record exists for this item in the selected warehouse")
    return bal


def _apply(
    db: Session,
    bal: InventoryBalance,
    txn_type: TxnType,
    user: User | None,
    *,
    on_hand_delta: Decimal = ZERO,
    reserved_delta: Decimal = ZERO,
    reference_type: str | None = None,
    reference_id: int | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> InventoryTransaction:
    new_on_hand = qty(bal.on_hand + on_hand_delta)
    new_reserved = qty(bal.reserved + reserved_delta)
    if new_on_hand < 0:
        raise BusinessRuleError(
            f"Insufficient stock: on hand {bal.on_hand}, change {on_hand_delta}",
            {"balance_id": bal.id, "on_hand": str(bal.on_hand)},
        )
    if new_reserved < 0:
        raise BusinessRuleError("Cannot release more than is reserved", {"balance_id": bal.id})
    if new_reserved > new_on_hand:
        raise BusinessRuleError(
            f"Insufficient available stock: available {bal.on_hand - bal.reserved}",
            {"balance_id": bal.id, "available": str(bal.on_hand - bal.reserved)},
        )
    bal.on_hand, bal.reserved = new_on_hand, new_reserved
    txn = InventoryTransaction(
        balance_id=bal.id,
        txn_type=txn_type,
        on_hand_delta=on_hand_delta,
        reserved_delta=reserved_delta,
        on_hand_after=new_on_hand,
        reserved_after=new_reserved,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        idempotency_key=idempotency_key,
        user_id=user.id if user else None,
    )
    db.add(txn)
    db.flush()
    return txn


def _replay(db: Session, key: str | None, txn_type: TxnType) -> InventoryTransaction | None:
    """Return the transaction previously created with this idempotency key, if any."""
    if not key:
        return None
    existing = (
        db.execute(select(InventoryTransaction).where(InventoryTransaction.idempotency_key == key)).unique().scalar_one_or_none()
    )
    if existing and existing.txn_type != txn_type:
        raise ConflictError("Idempotency key already used for a different operation")
    return existing


# --------------------------------------------------------------------------- receipts & adjustments


def receive(db: Session, user: User, data: ReceiptIn, idempotency_key: str | None) -> tuple[InventoryTransaction, bool]:
    """Receive raw material. Returns (transaction, created). Replays with the same key return the original.

    The key is checked *after* the balance row is locked, so a concurrent duplicate waits for the
    first request to commit and then sees its transaction.
    """
    material = get_or_404(db, Material, data.material_id)
    if not material.is_active:
        raise BusinessRuleError("Cannot receive an inactive material")
    wh = get_or_404(db, Warehouse, data.warehouse_id)
    if not wh.is_active:
        raise BusinessRuleError("Warehouse is inactive")
    if data.supplier_id is not None:
        get_or_404(db, Supplier, data.supplier_id)
    bal = lock_balance(db, wh.id, material_id=material.id, create=True)
    if existing := _replay(db, idempotency_key, TxnType.RECEIPT):
        return existing, False
    reason = "Goods receipt" + (f" ref {data.reference}" if data.reference else "") + (f": {data.notes}" if data.notes else "")
    txn = _apply(
        db,
        bal,
        TxnType.RECEIPT,
        user,
        on_hand_delta=data.quantity,
        reference_type="SUPPLIER" if data.supplier_id else "RECEIPT",
        reference_id=data.supplier_id,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    audit.record(
        db,
        user,
        "inventory.receive",
        "material",
        material.id,
        f"Received {data.quantity} {material.uom} of {material.sku} into {wh.code}",
        {"txn_id": txn.id, "reference": data.reference},
    )
    return txn, True


def adjust(db: Session, user: User, data: AdjustmentIn, idempotency_key: str | None) -> tuple[InventoryTransaction, bool]:
    get_or_404(db, Warehouse, data.warehouse_id)
    if data.item_type == ItemType.MATERIAL:
        item = get_or_404(db, Material, data.item_id)
        bal = lock_balance(db, data.warehouse_id, material_id=item.id, create=data.quantity_delta > 0)
    else:
        item = get_or_404(db, Product, data.item_id)
        bal = lock_balance(db, data.warehouse_id, product_id=item.id, create=data.quantity_delta > 0)
    if existing := _replay(db, idempotency_key, TxnType.ADJUSTMENT):
        return existing, False
    if data.quantity_delta < 0 and bal.on_hand + data.quantity_delta < bal.reserved:
        raise BusinessRuleError(
            "Adjustment would reduce stock below the reserved quantity; release reservations first",
            {"available": str(bal.available)},
        )
    txn = _apply(
        db,
        bal,
        TxnType.ADJUSTMENT,
        user,
        on_hand_delta=data.quantity_delta,
        reference_type="ADJUSTMENT",
        reason=data.reason,
        idempotency_key=idempotency_key,
    )
    audit.record(
        db,
        user,
        "inventory.adjust",
        data.item_type.lower(),
        item.id,
        f"Adjusted {item.sku} by {data.quantity_delta}: {data.reason}",
        {"txn_id": txn.id},
    )
    return txn, True


# --------------------------------------------------------------------------- job material reservations


def job_requirements(job: ProductionJob) -> dict[int, Decimal]:
    """Material quantity needed for the full planned quantity (single-level requirement model)."""
    return {pm.material_id: qty(pm.quantity_per_unit * job.planned_quantity) for pm in job.product.materials}


def units_to_produce(job: ProductionJob) -> Decimal:
    """Good units still to make: plan minus good output not rejected by QC (approved + pending + on hold)."""
    return max(ZERO, job.planned_quantity - (job.produced_quantity - job.qc_rejected_quantity))


def outstanding_requirements(job: ProductionJob) -> dict[int, Decimal]:
    """Material still needed to finish the job (replacements for QC rejects included)."""
    units = units_to_produce(job)
    return {pm.material_id: qty(pm.quantity_per_unit * units) for pm in job.product.materials}


def scrap_allowance() -> Decimal:
    from app.core.config import get_settings

    return Decimal(get_settings().scrap_allowance_pct) / Decimal("100")


def job_allocation_cap(job: ProductionJob, material_id: int) -> Decimal:
    """Most material a job may hold: plan + scrap allowance + replacements for scrapped/QC-rejected units."""
    pm = next((m for m in job.product.materials if m.material_id == material_id), None)
    if pm is None:
        raise BusinessRuleError("This material is not required by the job's product")
    units = job.planned_quantity * (1 + scrap_allowance()) + job.scrap_quantity + job.qc_rejected_quantity
    return qty(pm.quantity_per_unit * units)


def job_reservations(db: Session, job_id: int, active_only: bool = False) -> list[Reservation]:
    stmt = select(Reservation).where(Reservation.production_job_id == job_id).order_by(Reservation.id)
    if active_only:
        stmt = stmt.where(Reservation.status == ReservationStatus.ACTIVE)
    return list(db.execute(stmt).unique().scalars())


def material_held_by_job(db: Session, job_id: int) -> dict[int, dict[str, Decimal]]:
    """Per material: allocated (active remaining) and consumed."""
    out: dict[int, dict[str, Decimal]] = {}
    for r in job_reservations(db, job_id):
        d = out.setdefault(r.balance.material_id, {"allocated": ZERO, "consumed": ZERO})
        d["consumed"] += r.consumed_quantity
        if r.status == ReservationStatus.ACTIVE:
            d["allocated"] += r.remaining
    return out


def materials_ready(db: Session, job: ProductionJob) -> bool:
    """True when active allocations cover the material still needed to finish the job."""
    held = material_held_by_job(db, job.id)
    return all(held.get(mid, {}).get("allocated", ZERO) >= need for mid, need in outstanding_requirements(job).items())


def _check_job_open(job: ProductionJob) -> None:
    if job.status not in (JobStatus.PLANNED, JobStatus.IN_PROGRESS):
        raise BusinessRuleError(f"Cannot allocate material to a job in status {job.status}")


def reserve_for_job(
    db: Session,
    user: User,
    job: ProductionJob,
    material_id: int,
    warehouse_id: int,
    quantity: Decimal,
) -> Reservation:
    _check_job_open(job)
    cap = job_allocation_cap(job, material_id)
    held = material_held_by_job(db, job.id).get(material_id, {"allocated": ZERO, "consumed": ZERO})
    if held["allocated"] + held["consumed"] + quantity > cap:
        raise BusinessRuleError(
            f"Reservation exceeds the job requirement (max additional {qty(cap - held['allocated'] - held['consumed'])})",
            {"cap": str(cap)},
        )
    bal = lock_balance(db, warehouse_id, material_id=material_id)
    if quantity > bal.available:
        raise BusinessRuleError(
            f"Cannot reserve {quantity}: only {bal.available} available in this warehouse",
            {"available": str(bal.available)},
        )
    res = Reservation(balance_id=bal.id, production_job_id=job.id, quantity=quantity, created_by_id=user.id)
    db.add(res)
    db.flush()
    _apply(
        db,
        bal,
        TxnType.RESERVE,
        user,
        reserved_delta=quantity,
        reference_type="PRODUCTION_JOB",
        reference_id=job.id,
        reason=f"Reserved for {job.job_number} (reservation {res.id})",
    )
    audit.record(
        db,
        user,
        "inventory.reserve",
        "production_job",
        job.id,
        f"Reserved {quantity} of material {material_id} for {job.job_number}",
        {"reservation_id": res.id},
    )
    return res


def auto_allocate(db: Session, user: User, job: ProductionJob, warehouse_id: int | None = None) -> list[Reservation]:
    """Allocate every material shortfall for a job from the warehouses with most stock.

    All-or-nothing on the base requirement; the scrap allowance is added on top when stock permits.
    """
    _check_job_open(job)
    held = material_held_by_job(db, job.id)
    plan: list[tuple[int, int, Decimal]] = []
    shortages = []
    allowance = 1 + scrap_allowance()
    for material_id, need in outstanding_requirements(job).items():
        h = held.get(material_id, {"allocated": ZERO, "consumed": ZERO})
        base_short = need - h["allocated"]
        if base_short <= 0:
            continue
        room = job_allocation_cap(job, material_id) - h["allocated"] - h["consumed"]
        short = qty(max(base_short, min(need * allowance - h["allocated"], room)))
        stmt = select(InventoryBalance).where(InventoryBalance.material_id == material_id)
        if warehouse_id:
            stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
        balances = sorted(db.execute(stmt).unique().scalars(), key=lambda b: b.available, reverse=True)
        remaining = short
        for b in balances:
            take = min(b.available, remaining)
            if take > 0:
                plan.append((material_id, b.warehouse_id, take))
                remaining -= take
            if remaining <= 0:
                break
        if short - remaining < base_short:
            mat = db.get(Material, material_id)
            shortages.append(
                {
                    "material_id": material_id,
                    "sku": mat.sku,
                    "required": str(base_short),
                    "missing": str(base_short - (short - remaining)),
                }
            )
    if shortages:
        raise BusinessRuleError("Insufficient material available to allocate this job", {"shortages": shortages})
    return [reserve_for_job(db, user, job, m, w, q) for m, w, q in plan]


def release_reservation(db: Session, user: User, reservation: Reservation, reason: str) -> Reservation:
    if reservation.status != ReservationStatus.ACTIVE:
        raise BusinessRuleError(f"Reservation is already {reservation.status}")
    bal = lock_balance(
        db,
        reservation.balance.warehouse_id,
        material_id=reservation.balance.material_id,
        product_id=reservation.balance.product_id,
    )
    db.refresh(reservation)
    remaining = reservation.remaining
    if remaining > 0:
        ref_type, ref_id = (
            ("PRODUCTION_JOB", reservation.production_job_id)
            if reservation.production_job_id
            else ("DELIVERY", reservation.delivery_id)
        )
        _apply(
            db,
            bal,
            TxnType.RELEASE,
            user,
            reserved_delta=-remaining,
            reference_type=ref_type,
            reference_id=ref_id,
            reason=f"Released reservation {reservation.id}: {reason}",
        )
    reservation.status = ReservationStatus.RELEASED
    reservation.closed_at = datetime.now(UTC)
    audit.record(db, user, "inventory.release", "reservation", reservation.id, f"Released {remaining}: {reason}")
    return reservation


def release_all_for_job(db: Session, user: User, job: ProductionJob, reason: str) -> None:
    for r in job_reservations(db, job.id, active_only=True):
        release_reservation(db, user, r, reason)


def consume_for_job(db: Session, user: User, job: ProductionJob, units: Decimal, batch_ref: str) -> None:
    """Consume material for ``units`` produced (good + scrap) from the job's active reservations."""
    for pm in job.product.materials:
        need = qty(pm.quantity_per_unit * units)
        reservations = [r for r in job_reservations(db, job.id, active_only=True) if r.balance.material_id == pm.material_id]
        if sum((r.remaining for r in reservations), ZERO) < need:
            raise BusinessRuleError(
                f"Not enough {pm.material.sku} allocated to record this output; allocate more material first",
                {"material_id": pm.material_id, "required": str(need)},
            )
        for r in reservations:
            if need <= 0:
                break
            take = min(r.remaining, need)
            bal = lock_balance(db, r.balance.warehouse_id, material_id=pm.material_id)
            _apply(
                db,
                bal,
                TxnType.CONSUME,
                user,
                on_hand_delta=-take,
                reserved_delta=-take,
                reference_type="PRODUCTION_JOB",
                reference_id=job.id,
                reason=f"Consumed by {job.job_number} batch {batch_ref}",
            )
            r.consumed_quantity = qty(r.consumed_quantity + take)
            if r.remaining == 0:
                r.status = ReservationStatus.CONSUMED
                r.closed_at = datetime.now(UTC)
            need -= take


# --------------------------------------------------------------------------- finished goods


def produce_finished(db: Session, user: User, job: ProductionJob, quantity: Decimal, inspection_number: str) -> None:
    bal = lock_balance(db, job.output_warehouse_id, product_id=job.product_id, create=True)
    _apply(
        db,
        bal,
        TxnType.PRODUCE,
        user,
        on_hand_delta=quantity,
        reference_type="PRODUCTION_JOB",
        reference_id=job.id,
        reason=f"QC-approved output of {job.job_number} ({inspection_number})",
    )


def reserve_for_delivery(
    db: Session, user: User, delivery_id: int, product_id: int, warehouse_id: int, quantity: Decimal, delivery_number: str
) -> Reservation:
    bal = lock_balance(db, warehouse_id, product_id=product_id)
    if quantity > bal.available:
        raise BusinessRuleError(
            f"Only {bal.available} finished units available in the warehouse for this product",
            {"product_id": product_id, "available": str(bal.available)},
        )
    res = Reservation(balance_id=bal.id, delivery_id=delivery_id, quantity=quantity, created_by_id=user.id)
    db.add(res)
    db.flush()
    _apply(
        db,
        bal,
        TxnType.RESERVE,
        user,
        reserved_delta=quantity,
        reference_type="DELIVERY",
        reference_id=delivery_id,
        reason=f"Reserved for {delivery_number}",
    )
    return res


def dispatch_reservation(db: Session, user: User, res: Reservation, delivery_number: str) -> None:
    bal = lock_balance(db, res.balance.warehouse_id, product_id=res.balance.product_id)
    _apply(
        db,
        bal,
        TxnType.DISPATCH,
        user,
        on_hand_delta=-res.remaining,
        reserved_delta=-res.remaining,
        reference_type="DELIVERY",
        reference_id=res.delivery_id,
        reason=f"Dispatched on {delivery_number}",
    )
    res.consumed_quantity = res.quantity
    res.status = ReservationStatus.CONSUMED
    res.closed_at = datetime.now(UTC)


def return_to_stock(
    db: Session, user: User, product_id: int, warehouse_id: int, quantity: Decimal, delivery_id: int, reason: str
) -> None:
    bal = lock_balance(db, warehouse_id, product_id=product_id, create=True)
    _apply(
        db, bal, TxnType.RETURN, user, on_hand_delta=quantity, reference_type="DELIVERY", reference_id=delivery_id, reason=reason
    )


# --------------------------------------------------------------------------- queries


def material_totals(db: Session) -> dict[int, Decimal]:
    rows = db.execute(
        select(InventoryBalance.material_id, func.sum(InventoryBalance.on_hand - InventoryBalance.reserved))
        .where(InventoryBalance.material_id.is_not(None))
        .group_by(InventoryBalance.material_id)
    ).all()
    return {mid: total for mid, total in rows}


def low_stock_materials(db: Session) -> list[dict]:
    totals = material_totals(db)
    out = []
    for m in db.execute(select(Material).where(Material.is_active.is_(True)).order_by(Material.sku)).unique().scalars():
        available = totals.get(m.id, ZERO)
        if available < m.reorder_level:
            out.append(
                {
                    "material_id": m.id,
                    "sku": m.sku,
                    "name": m.name,
                    "uom": m.uom,
                    "category": m.category,
                    "available": available,
                    "reorder_level": m.reorder_level,
                    "shortfall": m.reorder_level - available,
                    "preferred_supplier": m.preferred_supplier.company_name if m.preferred_supplier else None,
                }
            )
    return out


def balance_stmt(item_type: str | None, q: str | None, category: str | None, warehouse_id: int | None, supplier_id: int | None):
    stmt = (
        select(InventoryBalance)
        .outerjoin(Material, InventoryBalance.material_id == Material.id)
        .outerjoin(Product, InventoryBalance.product_id == Product.id)
    )
    if item_type:
        stmt = stmt.where(InventoryBalance.item_type == item_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Material.sku.ilike(like), Material.name.ilike(like), Product.sku.ilike(like), Product.name.ilike(like))
        )
    if category:
        stmt = stmt.where(Material.category == category)
    if warehouse_id:
        stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
    if supplier_id:
        stmt = stmt.where(Material.preferred_supplier_id == supplier_id)
    return stmt.order_by(InventoryBalance.item_type, func.coalesce(Material.sku, Product.sku), InventoryBalance.warehouse_id)


def decorate_balances(db: Session, balances: list[InventoryBalance]) -> list[dict]:
    totals = material_totals(db)
    out = []
    for b in balances:
        d = {
            "id": b.id,
            "item_type": b.item_type,
            "material": b.material,
            "product": b.product,
            "warehouse": b.warehouse,
            "on_hand": b.on_hand,
            "reserved": b.reserved,
            "available": b.available,
            "updated_at": b.updated_at,
            "reorder_level": None,
            "category": None,
            "low_stock": False,
        }
        if b.material:
            d["reorder_level"] = b.material.reorder_level
            d["category"] = b.material.category
            d["low_stock"] = totals.get(b.material_id, ZERO) < b.material.reorder_level
        else:
            d["category"] = "Finished goods"
        out.append(d)
    return out


def reconcile(db: Session) -> list[dict]:
    """Compare every balance against the sum of its ledger entries."""
    sums = dict(
        (bid, (oh, rs))
        for bid, oh, rs in db.execute(
            select(
                InventoryTransaction.balance_id,
                func.sum(InventoryTransaction.on_hand_delta),
                func.sum(InventoryTransaction.reserved_delta),
            ).group_by(InventoryTransaction.balance_id)
        ).all()
    )
    rows = []
    for b in db.execute(select(InventoryBalance).order_by(InventoryBalance.id)).unique().scalars():
        oh, rs = sums.get(b.id, (ZERO, ZERO))
        rows.append(
            {
                "balance_id": b.id,
                "on_hand": b.on_hand,
                "ledger_on_hand": oh,
                "reserved": b.reserved,
                "ledger_reserved": rs,
                "ok": b.on_hand == oh and b.reserved == rs,
            }
        )
    return rows


def get_reservation(db: Session, reservation_id: int) -> Reservation:
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise NotFoundError(f"Reservation {reservation_id} not found")
    return res


def reservation_dict(r: Reservation) -> dict:
    return {
        "id": r.id,
        "balance": {
            "id": r.balance.id,
            "item_type": r.balance.item_type,
            "material": r.balance.material,
            "product": r.balance.product,
            "warehouse": r.balance.warehouse,
            "on_hand": r.balance.on_hand,
            "reserved": r.balance.reserved,
            "available": r.balance.available,
            "updated_at": r.balance.updated_at,
        },
        "production_job_id": r.production_job_id,
        "delivery_id": r.delivery_id,
        "quantity": r.quantity,
        "consumed_quantity": r.consumed_quantity,
        "remaining": r.remaining,
        "status": r.status,
        "created_at": r.created_at,
        "closed_at": r.closed_at,
    }
