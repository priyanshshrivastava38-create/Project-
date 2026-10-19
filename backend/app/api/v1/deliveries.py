from fastapi import APIRouter, Depends

from app.core.deps import DB, require
from app.models import Delivery, User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.delivery import (
    CancelIn,
    ConfirmDeliveryIn,
    DeliveryCreate,
    DeliveryOut,
    DispatchableOrder,
    DispatchIn,
    FailDeliveryIn,
)
from app.services import deliveries as svc
from app.services.common import get_or_404, paginate

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=Page[DeliveryOut])
def list_deliveries(
    db: DB,
    pp: PageParams = Depends(),
    status: str | None = None,
    order_id: int | None = None,
    q: str | None = None,
    _: User = Depends(require(P.DELIVERIES_READ)),
) -> dict:
    items, total = paginate(db, svc.delivery_stmt(status, order_id, q), pp.page, pp.page_size)
    return {"items": [svc.to_out(d) for d in items], "total": total, "page": pp.page, "page_size": pp.page_size}


@router.get("/dispatchable", response_model=list[DispatchableOrder])
def dispatchable(db: DB, _: User = Depends(require(P.DELIVERIES_READ))):
    """Orders with QC-approved units not yet allocated to a delivery."""
    return svc.dispatchable_orders(db)


@router.post("", response_model=DeliveryOut, status_code=201)
def create(body: DeliveryCreate, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    return svc.to_out(svc.create_delivery(db, user, body))


@router.get("/{delivery_id}", response_model=DeliveryOut)
def get(delivery_id: int, db: DB, _: User = Depends(require(P.DELIVERIES_READ))):
    return svc.to_out(get_or_404(db, Delivery, delivery_id, "Delivery"))


@router.post("/{delivery_id}/ready", response_model=DeliveryOut)
def ready(delivery_id: int, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    """Reserve the finished goods for this delivery (fails if stock is not available)."""
    return svc.to_out(svc.mark_ready(db, user, delivery_id))


@router.post("/{delivery_id}/dispatch", response_model=DeliveryOut)
def dispatch(delivery_id: int, body: DispatchIn, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    return svc.to_out(svc.dispatch(db, user, delivery_id, body))


@router.post("/{delivery_id}/in-transit", response_model=DeliveryOut)
def in_transit(delivery_id: int, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    return svc.to_out(svc.mark_in_transit(db, user, delivery_id))


@router.post("/{delivery_id}/confirm-delivery", response_model=DeliveryOut)
def confirm(delivery_id: int, body: ConfirmDeliveryIn, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    """Requires the name of the person who received the goods."""
    return svc.to_out(svc.confirm_delivery(db, user, delivery_id, body))


@router.post("/{delivery_id}/fail", response_model=DeliveryOut)
def fail(delivery_id: int, body: FailDeliveryIn, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    return svc.to_out(svc.fail_delivery(db, user, delivery_id, body.reason, body.return_to_stock))


@router.post("/{delivery_id}/cancel", response_model=DeliveryOut)
def cancel(delivery_id: int, body: CancelIn, db: DB, user: User = Depends(require(P.DELIVERIES_WRITE))):
    return svc.to_out(svc.cancel_delivery(db, user, delivery_id, body.reason))
