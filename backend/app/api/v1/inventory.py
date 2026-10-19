from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import select

from app.core.deps import DB, require
from app.models import InventoryBalance, InventoryTransaction, Material, Product, ProductionJob, User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.inventory import (
    AdjustmentIn,
    BalanceOut,
    ReceiptIn,
    ReconciliationRow,
    ReservationIn,
    ReservationOut,
    TransactionOut,
)
from app.schemas.order import StatusChange
from app.services import inventory as svc
from app.services.common import get_or_404, paginate

router = APIRouter(prefix="/inventory", tags=["inventory"])
IdemKey = Header(
    default=None,
    alias="Idempotency-Key",
    max_length=80,
    description="Repeat a request with the same key to get the original result instead of a duplicate movement",
)


def _txn_out(db, t: InventoryTransaction) -> dict:
    return {
        **{
            k: getattr(t, k)
            for k in (
                "id",
                "txn_type",
                "on_hand_delta",
                "reserved_delta",
                "on_hand_after",
                "reserved_after",
                "reference_type",
                "reference_id",
                "reason",
                "user",
                "created_at",
            )
        },
        "balance": svc.decorate_balances(db, [t.balance])[0],
    }


@router.get("", response_model=Page[BalanceOut])
def list_balances(
    db: DB,
    pp: PageParams = Depends(),
    item_type: str | None = None,
    q: str | None = None,
    category: str | None = None,
    warehouse_id: int | None = None,
    supplier_id: int | None = None,
    low_stock: bool = False,
    _: User = Depends(require(P.INVENTORY_READ)),
) -> dict:
    stmt = svc.balance_stmt(item_type, q, category, warehouse_id, supplier_id)
    if low_stock:
        low_ids = [m["material_id"] for m in svc.low_stock_materials(db)]
        stmt = stmt.where(InventoryBalance.material_id.in_(low_ids or [-1]))
    items, total = paginate(db, stmt, pp.page, pp.page_size)
    return {"items": svc.decorate_balances(db, items), "total": total, "page": pp.page, "page_size": pp.page_size}


@router.get("/low-stock")
def low_stock(db: DB, _: User = Depends(require(P.INVENTORY_READ))) -> list[dict]:
    return [{k: (format(v, "f") if hasattr(v, "quantize") else v) for k, v in m.items()} for m in svc.low_stock_materials(db)]


@router.get("/transactions", response_model=Page[TransactionOut])
def list_transactions(
    db: DB,
    pp: PageParams = Depends(),
    txn_type: str | None = None,
    material_id: int | None = None,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    q: str | None = None,
    _: User = Depends(require(P.INVENTORY_READ)),
) -> dict:
    stmt = (
        select(InventoryTransaction)
        .join(InventoryBalance, InventoryTransaction.balance_id == InventoryBalance.id)
        .outerjoin(Material, InventoryBalance.material_id == Material.id)
        .outerjoin(Product, InventoryBalance.product_id == Product.id)
    )
    if txn_type:
        stmt = stmt.where(InventoryTransaction.txn_type == txn_type)
    if material_id:
        stmt = stmt.where(InventoryBalance.material_id == material_id)
    if product_id:
        stmt = stmt.where(InventoryBalance.product_id == product_id)
    if warehouse_id:
        stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
    if reference_type:
        stmt = stmt.where(InventoryTransaction.reference_type == reference_type)
    if reference_id:
        stmt = stmt.where(InventoryTransaction.reference_id == reference_id)
    if q:
        stmt = stmt.where(
            Material.sku.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%") | InventoryTransaction.reason.ilike(f"%{q}%")
        )
    items, total = paginate(db, stmt.order_by(InventoryTransaction.id.desc()), pp.page, pp.page_size)
    return {"items": [_txn_out(db, t) for t in items], "total": total, "page": pp.page, "page_size": pp.page_size}


@router.post(
    "/receipts",
    response_model=TransactionOut,
    status_code=201,
    responses={200: {"description": "Replay of an earlier request with the same Idempotency-Key"}},
)
def receive(
    body: ReceiptIn,
    response: Response,
    db: DB,
    idempotency_key: str | None = IdemKey,
    user: User = Depends(require(P.INVENTORY_RECEIVE)),
):
    txn, created = svc.receive(db, user, body, idempotency_key)
    db.commit()
    if not created:
        response.status_code = 200
    return _txn_out(db, txn)


@router.post("/adjustments", response_model=TransactionOut, status_code=201)
def adjust(
    body: AdjustmentIn,
    response: Response,
    db: DB,
    idempotency_key: str | None = IdemKey,
    user: User = Depends(require(P.INVENTORY_ADJUST)),
):
    """Authorised stock correction. ``reason`` is mandatory and recorded in the ledger and audit log."""
    txn, created = svc.adjust(db, user, body, idempotency_key)
    db.commit()
    if not created:
        response.status_code = 200
    return _txn_out(db, txn)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(
    db: DB, production_job_id: int | None = None, status: str | None = None, _: User = Depends(require(P.INVENTORY_READ))
):
    from app.models import Reservation

    stmt = select(Reservation).order_by(Reservation.id.desc()).limit(500)
    if production_job_id:
        stmt = stmt.where(Reservation.production_job_id == production_job_id)
    if status:
        stmt = stmt.where(Reservation.status == status)
    return [svc.reservation_dict(r) for r in db.execute(stmt).unique().scalars()]


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def reserve(body: ReservationIn, db: DB, user: User = Depends(require(P.INVENTORY_RESERVE))):
    job = get_or_404(db, ProductionJob, body.production_job_id, "Job", lock=True)
    res = svc.reserve_for_job(db, user, job, body.material_id, body.warehouse_id, body.quantity)
    db.commit()
    return svc.reservation_dict(res)


@router.post("/reservations/{reservation_id}/release", response_model=ReservationOut)
def release(reservation_id: int, body: StatusChange, db: DB, user: User = Depends(require(P.INVENTORY_RESERVE))):
    res = svc.get_reservation(db, reservation_id)
    if res.delivery_id:
        from app.core.errors import BusinessRuleError

        raise BusinessRuleError("Delivery reservations are released by cancelling the delivery")
    get_or_404(db, ProductionJob, res.production_job_id, "Job", lock=True)
    svc.release_reservation(db, user, res, body.reason)
    db.commit()
    return svc.reservation_dict(res)


@router.get("/reconciliation", response_model=list[ReconciliationRow])
def reconciliation(db: DB, _: User = Depends(require(P.INVENTORY_ADJUST))):
    """Verify every balance equals the sum of its ledger entries."""
    return svc.reconcile(db)
