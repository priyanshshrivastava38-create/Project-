from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import DB, require
from app.models import AuditLog, User
from app.permissions.policy import P
from app.schemas.common import PageParams
from app.services import dashboard as svc
from app.services import inventory
from app.services.common import paginate

router = APIRouter(tags=["dashboard"])


def _json(v):
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json(x) for x in v]
    if hasattr(v, "quantize"):
        return format(v, "f")
    return v


@router.get("/dashboard/summary")
def summary(
    db: DB, date_from: date | None = None, date_to: date | None = None, _: User = Depends(require(P.DASHBOARD_READ))
) -> dict:
    return _json(svc.summary(db, date_from, date_to))


@router.get("/dashboard/production")
def production(db: DB, days: int = Query(30, ge=7, le=180), _: User = Depends(require(P.DASHBOARD_READ))) -> dict:
    return svc.production_trend(db, days)


@router.get("/dashboard/inventory-alerts")
def inventory_alerts(db: DB, _: User = Depends(require(P.DASHBOARD_READ))) -> list[dict]:
    return _json(inventory.low_stock_materials(db))


@router.get("/reports/orders-by-customer")
def orders_by_customer(
    db: DB, date_from: date | None = None, date_to: date | None = None, _: User = Depends(require(P.REPORTS_READ))
) -> list[dict]:
    return svc.report_orders_by_customer(db, date_from, date_to)


@router.get("/reports/production-performance")
def production_performance(db: DB, _: User = Depends(require(P.REPORTS_READ))) -> dict:
    return svc.report_production_performance(db)


@router.get("/reports/quality")
def quality(db: DB, _: User = Depends(require(P.REPORTS_READ))) -> dict:
    return svc.report_quality(db)


@router.get("/reports/fulfillment")
def fulfillment(db: DB, _: User = Depends(require(P.REPORTS_READ))) -> list[dict]:
    return svc.report_fulfillment(db)


@router.get("/audit-logs")
def audit_logs(
    db: DB,
    pp: PageParams = Depends(),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    _: User = Depends(require(P.AUDIT_READ)),
) -> dict:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    items, total = paginate(db, stmt.order_by(AuditLog.id.desc()), pp.page, pp.page_size)
    return {
        "items": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "summary": a.summary,
                "details": a.details,
                "user": {"id": a.user.id, "full_name": a.user.full_name} if a.user else None,
                "created_at": a.created_at,
            }
            for a in items
        ],
        "total": total,
        "page": pp.page,
        "page_size": pp.page_size,
    }
