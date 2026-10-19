from datetime import date

from fastapi import APIRouter, Depends

from app.core.deps import DB, require
from app.models import CustomerOrder, User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.order import OrderCreate, OrderDetail, OrderOut, OrderSummary, OrderUpdate, StatusChange
from app.services import orders as svc
from app.services.common import paginate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=Page[OrderSummary])
def list_orders(
    db: DB,
    pp: PageParams = Depends(),
    customer_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    sort: str = "-order_date",
    _: User = Depends(require(P.ORDERS_READ)),
) -> dict:
    """Filter by customer, status (comma-separated), order date range and order number / customer name (``q``)."""
    items, total = paginate(db, svc.order_stmt(customer_id, status, date_from, date_to, q, sort), pp.page, pp.page_size)
    return {"items": items, "total": total, "page": pp.page, "page_size": pp.page_size}


@router.post("", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate, db: DB, user: User = Depends(require(P.ORDERS_WRITE))) -> CustomerOrder:
    """Creates a DRAFT order. Totals are always calculated on the server."""
    return svc.create_order(db, user, body)


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: int, db: DB, _: User = Depends(require(P.ORDERS_READ))):
    return svc.order_detail(db, order_id)


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(order_id: int, body: OrderUpdate, db: DB, user: User = Depends(require(P.ORDERS_WRITE))):
    return svc.update_order(db, user, order_id, body)


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(order_id: int, db: DB, user: User = Depends(require(P.ORDERS_WRITE))):
    return svc.confirm_order(db, user, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, body: StatusChange, db: DB, user: User = Depends(require(P.ORDERS_WRITE))):
    """DRAFT/CONFIRMED orders can be cancelled by sales; IN_PRODUCTION orders only by an admin and only before production starts."""
    return svc.cancel_order(db, user, order_id, body.reason)


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order(order_id: int, body: StatusChange, db: DB, user: User = Depends(require(P.ORDERS_REJECT))):
    return svc.reject_order(db, user, order_id, body.reason)
