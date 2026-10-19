"""Deliveries: PENDING -> READY_FOR_DISPATCH -> DISPATCHED -> IN_TRANSIT -> DELIVERED (+ CANCELLED / FAILED).

Quantities are validated against QC-approved output of the order line and against
finished-goods stock. The order row is locked while delivery quantities are checked, so
concurrent requests cannot allocate the same units twice.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, InvalidTransitionError
from app.models import CustomerOrder, Delivery, DeliveryItem, OrderItem, Reservation, User, Warehouse
from app.models.enums import DeliveryStatus, OrderStatus, ReservationStatus
from app.schemas.delivery import ConfirmDeliveryIn, DeliveryCreate, DispatchIn
from app.services import audit, inventory, orders
from app.services.common import get_or_404, next_number

ZERO = Decimal("0")
TRANSITIONS: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PENDING: {DeliveryStatus.READY_FOR_DISPATCH, DeliveryStatus.CANCELLED},
    DeliveryStatus.READY_FOR_DISPATCH: {DeliveryStatus.DISPATCHED, DeliveryStatus.CANCELLED},
    DeliveryStatus.DISPATCHED: {DeliveryStatus.IN_TRANSIT, DeliveryStatus.DELIVERED, DeliveryStatus.FAILED},
    DeliveryStatus.IN_TRANSIT: {DeliveryStatus.DELIVERED, DeliveryStatus.FAILED},
    DeliveryStatus.DELIVERED: set(),
    DeliveryStatus.FAILED: set(),
    DeliveryStatus.CANCELLED: set(),
}
SHIPPABLE_ORDER = (OrderStatus.IN_PRODUCTION, OrderStatus.PARTIALLY_FULFILLED)


def _move(db: Session, d: Delivery, target: DeliveryStatus, user: User, note: str = "") -> None:
    if target not in TRANSITIONS[DeliveryStatus(d.status)]:
        raise InvalidTransitionError(f"Delivery {d.delivery_number} cannot move from {d.status} to {target}")
    audit.record(
        db,
        user,
        f"delivery.{target.lower()}",
        "delivery",
        d.id,
        f"{d.delivery_number}: {d.status} -> {target}{(' — ' + note) if note else ''}",
    )
    d.status = target


def dispatchable_lines(db: Session, order: CustomerOrder) -> list[dict]:
    progress = orders.line_progress(db, order)
    out = []
    for i in order.items:
        p = progress[i.id]
        cap = min(p["approved_quantity"], i.quantity) - p["allocated_to_deliveries"]
        out.append(
            {
                "order_item_id": i.id,
                "sku": i.sku,
                "description": i.description,
                "ordered": i.quantity,
                "approved": p["approved_quantity"],
                "allocated": p["allocated_to_deliveries"],
                "dispatchable": max(ZERO, cap),
            }
        )
    return out


def create_delivery(db: Session, user: User, data: DeliveryCreate) -> Delivery:
    from app.services.production import default_output_warehouse

    order = get_or_404(db, CustomerOrder, data.order_id, "Order", lock=True)
    if order.status not in SHIPPABLE_ORDER:
        raise BusinessRuleError(f"Order {order.order_number} is {order.status}; nothing can be shipped yet")
    wh = get_or_404(db, Warehouse, data.warehouse_id, "Warehouse") if data.warehouse_id else default_output_warehouse(db)
    lines = {ln["order_item_id"]: ln for ln in dispatchable_lines(db, order)}
    seen = set()
    for it in data.items:
        if it.order_item_id not in lines:
            raise BusinessRuleError(f"Order item {it.order_item_id} does not belong to {order.order_number}")
        if it.order_item_id in seen:
            raise BusinessRuleError("Each order line may appear only once per delivery")
        seen.add(it.order_item_id)
        ln = lines[it.order_item_id]
        if it.quantity > ln["dispatchable"]:
            raise BusinessRuleError(
                f"{ln['sku']}: requested {it.quantity} but only {ln['dispatchable']} QC-approved units are not yet "
                f"allocated to a delivery",
                {"line": {k: str(v) for k, v in ln.items()}},
            )
    d = Delivery(
        delivery_number=next_number(db, "delivery_number_seq", "DEL-"),
        order_id=order.id,
        warehouse_id=wh.id,
        planned_dispatch_date=data.planned_dispatch_date,
        carrier=data.carrier,
        notes=data.notes,
        created_by_id=user.id,
        status=DeliveryStatus.PENDING,
    )
    d.items = [DeliveryItem(order_item_id=it.order_item_id, quantity=it.quantity) for it in data.items]
    db.add(d)
    db.flush()
    audit.record(db, user, "delivery.create", "delivery", d.id, f"Created {d.delivery_number} for {order.order_number}")
    db.commit()
    return d


def _lock(db: Session, delivery_id: int) -> Delivery:
    d = get_or_404(db, Delivery, delivery_id, "Delivery")
    get_or_404(db, CustomerOrder, d.order_id, "Order", lock=True)  # lock order first (global lock order)
    return get_or_404(db, Delivery, delivery_id, "Delivery", lock=True)


def _active_reservations(db: Session, d: Delivery) -> list[Reservation]:
    return list(
        db.execute(select(Reservation).where(Reservation.delivery_id == d.id, Reservation.status == ReservationStatus.ACTIVE))
        .unique()
        .scalars()
    )


def mark_ready(db: Session, user: User, delivery_id: int) -> Delivery:
    d = _lock(db, delivery_id)
    _move(db, d, DeliveryStatus.READY_FOR_DISPATCH, user)
    for it in d.items:
        inventory.reserve_for_delivery(db, user, d.id, it.order_item.product_id, d.warehouse_id, it.quantity, d.delivery_number)
    db.commit()
    return d


def dispatch(db: Session, user: User, delivery_id: int, data: DispatchIn) -> Delivery:
    d = _lock(db, delivery_id)
    if d.status == DeliveryStatus.DISPATCHED:
        raise InvalidTransitionError(f"{d.delivery_number} has already been dispatched")
    _move(db, d, DeliveryStatus.DISPATCHED, user, f"{data.carrier} {data.tracking_number}")
    for r in _active_reservations(db, d):
        inventory.dispatch_reservation(db, user, r, d.delivery_number)
    d.carrier, d.tracking_number, d.dispatched_at = data.carrier, data.tracking_number, datetime.now(UTC)
    db.commit()
    return d


def mark_in_transit(db: Session, user: User, delivery_id: int) -> Delivery:
    d = _lock(db, delivery_id)
    _move(db, d, DeliveryStatus.IN_TRANSIT, user)
    db.commit()
    return d


def confirm_delivery(db: Session, user: User, delivery_id: int, data: ConfirmDeliveryIn) -> Delivery:
    d = _lock(db, delivery_id)
    _move(db, d, DeliveryStatus.DELIVERED, user, f"received by {data.received_by}")
    delivered_at = data.delivered_at or datetime.now(UTC)
    if d.dispatched_at and delivered_at < d.dispatched_at:
        raise BusinessRuleError("delivered_at cannot be before the dispatch time")
    d.received_by, d.delivered_at, d.proof_of_delivery_ref = data.received_by, delivered_at, data.proof_of_delivery_ref
    if data.notes:
        d.notes = ((d.notes + "\n") if d.notes else "") + data.notes
    for it in d.items:
        item = db.get(OrderItem, it.order_item_id)
        item.delivered_quantity = item.delivered_quantity + it.quantity
    db.flush()
    order = db.get(CustomerOrder, d.order_id)
    db.refresh(order)
    orders.refresh_fulfillment(db, order, user)
    db.commit()
    return d


def fail_delivery(db: Session, user: User, delivery_id: int, reason: str, return_to_stock: bool) -> Delivery:
    d = _lock(db, delivery_id)
    _move(db, d, DeliveryStatus.FAILED, user, reason)
    d.failure_reason = reason
    if return_to_stock:
        for it in d.items:
            inventory.return_to_stock(
                db,
                user,
                it.order_item.product_id,
                d.warehouse_id,
                it.quantity,
                d.id,
                f"Returned from failed delivery {d.delivery_number}: {reason}",
            )
    db.commit()
    return d


def cancel_delivery(db: Session, user: User, delivery_id: int, reason: str) -> Delivery:
    d = _lock(db, delivery_id)
    _move(db, d, DeliveryStatus.CANCELLED, user, reason)
    for r in _active_reservations(db, d):
        inventory.release_reservation(db, user, r, f"{d.delivery_number} cancelled")
    d.failure_reason = reason
    db.commit()
    return d


def to_out(d: Delivery) -> dict:
    return {
        **{
            k: getattr(d, k)
            for k in (
                "id",
                "delivery_number",
                "order",
                "warehouse_id",
                "status",
                "planned_dispatch_date",
                "dispatched_at",
                "delivered_at",
                "carrier",
                "tracking_number",
                "received_by",
                "proof_of_delivery_ref",
                "failure_reason",
                "notes",
                "created_at",
                "updated_at",
            )
        },
        "customer_name": d.order.customer.company_name,
        "items": [
            {
                "id": i.id,
                "order_item_id": i.order_item_id,
                "sku": i.order_item.sku,
                "description": i.order_item.description,
                "quantity": i.quantity,
            }
            for i in d.items
        ],
    }


def delivery_stmt(status: str | None, order_id: int | None, q: str | None):
    stmt = select(Delivery).join(CustomerOrder, Delivery.order_id == CustomerOrder.id)
    if status:
        stmt = stmt.where(Delivery.status.in_(status.split(",")))
    if order_id:
        stmt = stmt.where(Delivery.order_id == order_id)
    if q:
        stmt = stmt.where(
            Delivery.delivery_number.ilike(f"%{q}%")
            | CustomerOrder.order_number.ilike(f"%{q}%")
            | Delivery.tracking_number.ilike(f"%{q}%")
        )
    return stmt.order_by(Delivery.id.desc())


def dispatchable_orders(db: Session) -> list[dict]:
    out = []
    for order in (
        db.execute(
            select(CustomerOrder)
            .where(CustomerOrder.status.in_(SHIPPABLE_ORDER))
            .order_by(CustomerOrder.required_date.asc().nulls_last())
        )
        .unique()
        .scalars()
    ):
        lines = [ln for ln in dispatchable_lines(db, order) if ln["dispatchable"] > 0]
        if lines:
            out.append(
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "customer_name": order.customer.company_name,
                    "required_date": order.required_date,
                    "lines": lines,
                }
            )
    return out
