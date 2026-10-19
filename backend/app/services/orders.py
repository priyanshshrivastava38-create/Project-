"""Customer orders: server-side totals and the order state machine."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, InvalidTransitionError, PermissionDeniedError
from app.models import (
    Customer,
    CustomerOrder,
    Delivery,
    DeliveryItem,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductionJob,
    User,
)
from app.models.enums import DeliveryStatus, JobStatus, OrderStatus, RecordStatus
from app.permissions.policy import P, has_permission
from app.schemas.order import OrderCreate, OrderItemIn, OrderUpdate
from app.services import audit
from app.services.common import get_or_404, money, next_number

ZERO = Decimal("0")

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.DRAFT: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.REJECTED},
    OrderStatus.CONFIRMED: {OrderStatus.IN_PRODUCTION, OrderStatus.CANCELLED},
    OrderStatus.IN_PRODUCTION: {OrderStatus.PARTIALLY_FULFILLED, OrderStatus.FULFILLED, OrderStatus.CANCELLED},
    OrderStatus.PARTIALLY_FULFILLED: {OrderStatus.FULFILLED},
    OrderStatus.FULFILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
}
INACTIVE_DELIVERY = (DeliveryStatus.CANCELLED, DeliveryStatus.FAILED)


def can_transition(current: str, target: OrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(OrderStatus(current), set())


def calculate_totals(lines: list[tuple[Decimal, Decimal]], tax_rate: Decimal) -> tuple[list[Decimal], Decimal, Decimal, Decimal]:
    """Return (line_totals, subtotal, tax_amount, total) from (quantity, unit_price) pairs."""
    line_totals = [money(q * p) for q, p in lines]
    subtotal = money(sum(line_totals, ZERO))
    tax = money(subtotal * tax_rate / Decimal("100"))
    return line_totals, subtotal, tax, money(subtotal + tax)


def _transition(db: Session, order: CustomerOrder, target: OrderStatus, user: User | None, reason: str | None = None) -> None:
    if not can_transition(order.status, target):
        raise InvalidTransitionError(f"Order {order.order_number} cannot move from {order.status} to {target}")
    order.history.append(
        OrderStatusHistory(from_status=order.status, to_status=target, reason=reason, changed_by_id=user.id if user else None)
    )
    audit.record(
        db,
        user,
        f"order.{target.lower()}",
        "order",
        order.id,
        f"Order {order.order_number}: {order.status} -> {target}",
        {"reason": reason},
    )
    order.status = target


def _build_items(db: Session, items: list[OrderItemIn]) -> list[OrderItem]:
    built = []
    for i, it in enumerate(items, start=1):
        product = get_or_404(db, Product, it.product_id, "Product")
        if not product.is_active:
            raise BusinessRuleError(f"Product {product.sku} is inactive")
        price = it.unit_price if it.unit_price is not None else product.unit_price
        built.append(
            OrderItem(
                line_number=i,
                product_id=product.id,
                sku=product.sku,
                description=it.description or product.name,
                quantity=it.quantity,
                unit_price=price,
                line_total=ZERO,
            )
        )
    return built


def _apply_totals(order: CustomerOrder) -> None:
    line_totals, order.subtotal, order.tax_amount, order.total = calculate_totals(
        [(i.quantity, i.unit_price) for i in order.items], order.tax_rate
    )
    for item, lt in zip(order.items, line_totals, strict=True):
        item.line_total = lt


def _check_customer(db: Session, customer_id: int) -> Customer:
    c = get_or_404(db, Customer, customer_id, "Customer")
    if c.status != RecordStatus.ACTIVE:
        raise BusinessRuleError(f"Customer {c.code} is inactive")
    return c


def create_order(db: Session, user: User, data: OrderCreate) -> CustomerOrder:
    _check_customer(db, data.customer_id)
    order_date = data.order_date or date.today()
    if data.required_date and data.required_date < order_date:
        raise BusinessRuleError("required_date cannot be before order_date")
    order = CustomerOrder(
        order_number=next_number(db, "order_number_seq", "SO-"),
        customer_id=data.customer_id,
        order_date=order_date,
        required_date=data.required_date,
        currency=data.currency,
        tax_rate=data.tax_rate if data.tax_rate is not None else Decimal(get_settings().default_tax_rate),
        notes=data.notes,
        created_by_id=user.id,
        status=OrderStatus.DRAFT,
    )
    order.items = _build_items(db, data.items)
    _apply_totals(order)
    db.add(order)
    db.flush()
    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=None, to_status=OrderStatus.DRAFT, reason="Order created", changed_by_id=user.id
        )
    )
    audit.record(db, user, "order.create", "order", order.id, f"Created order {order.order_number} total {order.total}")
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, user: User, order_id: int, data: OrderUpdate) -> CustomerOrder:
    order = get_or_404(db, CustomerOrder, order_id, "Order", lock=True)
    changes = data.model_dump(exclude_unset=True)
    if order.status != OrderStatus.DRAFT:
        if order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FULFILLED):
            raise BusinessRuleError(f"Order {order.order_number} is {order.status} and can no longer be edited")
        if set(changes) - {"notes"}:
            raise BusinessRuleError("Only notes can be changed after an order is confirmed")
    if "customer_id" in changes:
        _check_customer(db, changes["customer_id"])
        order.customer_id = changes["customer_id"]
    for f in ("required_date", "currency", "notes"):
        if f in changes:
            setattr(order, f, changes[f])
    if "tax_rate" in changes and changes["tax_rate"] is not None:
        order.tax_rate = changes["tax_rate"]
    if order.required_date and order.required_date < order.order_date:
        raise BusinessRuleError("required_date cannot be before order_date")
    if data.items is not None:
        order.items.clear()
        db.flush()
        order.items.extend(_build_items(db, data.items))
    _apply_totals(order)
    audit.record(db, user, "order.update", "order", order.id, f"Updated order {order.order_number}", {"fields": sorted(changes)})
    db.commit()
    db.refresh(order)
    return order


def confirm_order(db: Session, user: User, order_id: int) -> CustomerOrder:
    order = get_or_404(db, CustomerOrder, order_id, "Order", lock=True)
    _check_customer(db, order.customer_id)
    if not order.items:
        raise BusinessRuleError("An order needs at least one line item")
    _transition(db, order, OrderStatus.CONFIRMED, user, "Order confirmed")
    db.commit()
    return order


def reject_order(db: Session, user: User, order_id: int, reason: str) -> CustomerOrder:
    order = get_or_404(db, CustomerOrder, order_id, "Order", lock=True)
    _transition(db, order, OrderStatus.REJECTED, user, reason)
    db.commit()
    return order


def cancel_order(db: Session, user: User, order_id: int, reason: str) -> CustomerOrder:
    from app.services import inventory  # local import avoids a cycle

    order = get_or_404(db, CustomerOrder, order_id, "Order", lock=True)
    if order.status == OrderStatus.IN_PRODUCTION:
        if not has_permission(user.role, P.ORDERS_CANCEL_IN_PRODUCTION):
            raise PermissionDeniedError("Only an administrator can cancel an order that is in production")
        jobs = list(
            db.execute(select(ProductionJob).where(ProductionJob.order_id == order.id).with_for_update(of=ProductionJob))
            .unique()
            .scalars()
        )
        if any(j.status not in (JobStatus.PLANNED, JobStatus.CANCELLED) for j in jobs):
            raise BusinessRuleError("Production has started on this order; it cannot be cancelled")
        if db.execute(
            select(func.count())
            .select_from(Delivery)
            .where(Delivery.order_id == order.id, Delivery.status.not_in(INACTIVE_DELIVERY))
        ).scalar_one():
            raise BusinessRuleError("The order has active deliveries")
        for j in jobs:
            if j.status == JobStatus.PLANNED:
                inventory.release_all_for_job(db, user, j, f"Order {order.order_number} cancelled")
                j.status = JobStatus.CANCELLED
    _transition(db, order, OrderStatus.CANCELLED, user, reason)
    db.commit()
    return order


def mark_in_production(db: Session, order: CustomerOrder, user: User) -> None:
    if order.status == OrderStatus.CONFIRMED:
        _transition(db, order, OrderStatus.IN_PRODUCTION, user, "First production job created")


def refresh_fulfillment(db: Session, order: CustomerOrder, user: User) -> None:
    """Derive fulfillment from confirmed delivered quantities only."""
    if all(i.delivered_quantity >= i.quantity for i in order.items):
        target = OrderStatus.FULFILLED
    elif any(i.delivered_quantity > 0 for i in order.items):
        target = OrderStatus.PARTIALLY_FULFILLED
    else:
        return
    if order.status != target:
        _transition(db, order, target, user, "Delivery confirmed")


def line_progress(db: Session, order: CustomerOrder) -> dict[int, dict[str, Decimal]]:
    """Per order line: planned, approved (passed QC) and allocated to active deliveries."""
    out = {i.id: {"planned_quantity": ZERO, "approved_quantity": ZERO, "allocated_to_deliveries": ZERO} for i in order.items}
    for item_id, planned, approved in db.execute(
        select(ProductionJob.order_item_id, func.sum(ProductionJob.planned_quantity), func.sum(ProductionJob.approved_quantity))
        .where(ProductionJob.order_id == order.id, ProductionJob.status != JobStatus.CANCELLED)
        .group_by(ProductionJob.order_item_id)
    ).all():
        out[item_id]["planned_quantity"] = planned
        out[item_id]["approved_quantity"] = approved
    for item_id, allocated in db.execute(
        select(DeliveryItem.order_item_id, func.sum(DeliveryItem.quantity))
        .join(Delivery)
        .where(Delivery.order_id == order.id, Delivery.status.not_in(INACTIVE_DELIVERY))
        .group_by(DeliveryItem.order_item_id)
    ).all():
        out[item_id]["allocated_to_deliveries"] = allocated
    return out


def order_detail(db: Session, order_id: int) -> dict:
    order = get_or_404(db, CustomerOrder, order_id, "Order")
    progress = line_progress(db, order)
    jobs = list(
        db.execute(select(ProductionJob).where(ProductionJob.order_id == order.id).order_by(ProductionJob.id)).unique().scalars()
    )
    deliveries = list(db.execute(select(Delivery).where(Delivery.order_id == order.id).order_by(Delivery.id)).unique().scalars())
    from app.schemas.order import OrderItemOut, OrderOut

    base = OrderOut.model_validate(order).model_dump()
    base["item_progress"] = [{**OrderItemOut.model_validate(i).model_dump(), **progress[i.id]} for i in order.items]
    base["jobs"] = jobs
    base["deliveries"] = deliveries
    return base


def order_stmt(
    customer_id: int | None, status: str | None, date_from: date | None, date_to: date | None, q: str | None, sort: str
):
    stmt = select(CustomerOrder).join(Customer)
    if customer_id:
        stmt = stmt.where(CustomerOrder.customer_id == customer_id)
    if status:
        stmt = stmt.where(CustomerOrder.status.in_(status.split(",")))
    if date_from:
        stmt = stmt.where(CustomerOrder.order_date >= date_from)
    if date_to:
        stmt = stmt.where(CustomerOrder.order_date <= date_to)
    if q:
        stmt = stmt.where(CustomerOrder.order_number.ilike(f"%{q}%") | Customer.company_name.ilike(f"%{q}%"))
    cols = {
        "order_date": CustomerOrder.order_date,
        "total": CustomerOrder.total,
        "order_number": CustomerOrder.id,
        "required_date": CustomerOrder.required_date,
        "created_at": CustomerOrder.created_at,
    }
    col = cols.get(sort.lstrip("-"))
    if col is None:
        raise BusinessRuleError(f"Unsupported sort field '{sort}'", {"allowed": list(cols)})
    return stmt.order_by(col.desc() if sort.startswith("-") else col.asc(), CustomerOrder.id.desc())
