"""Dashboard and report queries. Every number is computed from the database."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Customer, CustomerOrder, Delivery, OrderItem, ProductionJob, QualityInspection
from app.models.enums import DeliveryStatus, InspectionOutcome, JobStatus, OrderStatus
from app.services import inventory
from app.services.deliveries import dispatchable_orders

ZERO = Decimal("0")


def _order_filter(stmt, date_from: date | None, date_to: date | None):
    if date_from:
        stmt = stmt.where(CustomerOrder.order_date >= date_from)
    if date_to:
        stmt = stmt.where(CustomerOrder.order_date <= date_to)
    return stmt


def summary(db: Session, date_from: date | None = None, date_to: date | None = None) -> dict:
    by_status = dict(
        db.execute(
            _order_filter(select(CustomerOrder.status, func.count()).group_by(CustomerOrder.status), date_from, date_to)
        ).all()
    )
    jobs = db.execute(select(ProductionJob).where(ProductionJob.status == JobStatus.IN_PROGRESS)).unique().scalars().all()
    pending_qc = sum(
        1
        for j in jobs
        if j.current_stage
        and j.current_stage.stage_code == "QUALITY_INSPECTION"
        and (j.pending_inspection_quantity > 0 or j.hold_quantity > 0)
    )
    overdue = db.execute(
        select(func.count())
        .select_from(ProductionJob)
        .where(ProductionJob.status.in_([JobStatus.PLANNED, JobStatus.IN_PROGRESS]), ProductionJob.target_date < date.today())
    ).scalar_one()
    in_transit = db.execute(
        select(func.count())
        .select_from(Delivery)
        .where(Delivery.status.in_([DeliveryStatus.DISPATCHED, DeliveryStatus.IN_TRANSIT]))
    ).scalar_one()
    revenue = db.execute(
        _order_filter(
            select(func.coalesce(func.sum(CustomerOrder.total), 0)).where(
                CustomerOrder.status.not_in([OrderStatus.DRAFT, OrderStatus.CANCELLED, OrderStatus.REJECTED])
            ),
            date_from,
            date_to,
        )
    ).scalar_one()
    return {
        "total_orders": sum(by_status.values()),
        "orders_awaiting_production": by_status.get(OrderStatus.CONFIRMED, 0),
        "active_production_jobs": len(jobs),
        "overdue_jobs": overdue,
        "pending_quality_inspections": pending_qc,
        "low_stock_alerts": len(inventory.low_stock_materials(db)),
        "orders_ready_for_dispatch": len(dispatchable_orders(db)),
        "deliveries_in_transit": in_transit,
        "booked_order_value": revenue,
        "order_status_distribution": [{"status": s.value, "count": by_status.get(s, 0)} for s in OrderStatus],
        "recent_activity": recent_activity(db, 12),
    }


def recent_activity(db: Session, limit: int = 12) -> list[dict]:
    rows = (
        db.execute(
            select(AuditLog)
            .where(~AuditLog.action.in_(["auth.login", "document.download"]))
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        .unique()
        .scalars()
    )
    return [
        {
            "id": a.id,
            "action": a.action,
            "summary": a.summary,
            "user": a.user.full_name if a.user else "system",
            "created_at": a.created_at,
        }
        for a in rows
    ]


def production_trend(db: Session, days: int = 30) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date_trunc("day", ProductionJob.actual_completion_at)
    rows = db.execute(
        select(
            day,
            func.count(),
            func.sum(ProductionJob.approved_quantity),
            func.sum(case((func.date(ProductionJob.actual_completion_at) <= ProductionJob.target_date, 1), else_=0)),
        )
        .where(ProductionJob.status == JobStatus.COMPLETED, ProductionJob.actual_completion_at >= since)
        .group_by(day)
        .order_by(day)
    ).all()
    completed = {r[0].date(): r for r in rows}
    series = []
    for i in range(days, -1, -1):
        d = (datetime.now(UTC) - timedelta(days=i)).date()
        r = completed.get(d)
        series.append(
            {
                "date": d.isoformat(),
                "jobs_completed": r[1] if r else 0,
                "units_approved": str(r[2]) if r else "0",
                "on_time": r[3] if r else 0,
            }
        )
    by_status = dict(db.execute(select(ProductionJob.status, func.count()).group_by(ProductionJob.status)).all())
    return {"days": days, "series": series, "job_status": [{"status": s.value, "count": by_status.get(s, 0)} for s in JobStatus]}


def report_orders_by_customer(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    stmt = (
        select(Customer.id, Customer.company_name, func.count(CustomerOrder.id), func.coalesce(func.sum(CustomerOrder.total), 0))
        .join(CustomerOrder, CustomerOrder.customer_id == Customer.id)
        .where(CustomerOrder.status.not_in([OrderStatus.CANCELLED, OrderStatus.REJECTED]))
        .group_by(Customer.id, Customer.company_name)
        .order_by(func.sum(CustomerOrder.total).desc())
    )
    return [
        {"customer_id": r[0], "customer": r[1], "orders": r[2], "total_value": str(r[3])}
        for r in db.execute(_order_filter(stmt, date_from, date_to)).all()
    ]


def report_production_performance(db: Session) -> dict:
    jobs = db.execute(select(ProductionJob).where(ProductionJob.status == JobStatus.COMPLETED)).unique().scalars().all()
    on_time = sum(1 for j in jobs if j.target_date and j.actual_completion_at and j.actual_completion_at.date() <= j.target_date)
    produced = sum((j.produced_quantity + j.scrap_quantity for j in jobs), ZERO)
    rejected = sum((j.rejected_quantity for j in jobs), ZERO)
    return {
        "completed_jobs": len(jobs),
        "on_time_jobs": on_time,
        "on_time_rate": round(on_time / len(jobs) * 100, 1) if jobs else None,
        "units_processed": str(produced),
        "units_rejected": str(rejected),
        "yield_rate": round(float((produced - rejected) / produced * 100), 1) if produced else None,
        "jobs": [
            {
                "job_number": j.job_number,
                "product": j.product.sku,
                "planned": str(j.planned_quantity),
                "approved": str(j.approved_quantity),
                "rejected": str(j.rejected_quantity),
                "target_date": j.target_date,
                "completed": j.actual_completion_at,
                "on_time": bool(j.target_date and j.actual_completion_at and j.actual_completion_at.date() <= j.target_date),
            }
            for j in sorted(jobs, key=lambda j: j.actual_completion_at, reverse=True)[:50]
        ],
    }


def report_quality(db: Session) -> dict:
    rows = db.execute(
        select(
            QualityInspection.outcome,
            func.count(),
            func.sum(QualityInspection.quantity_inspected),
            func.sum(QualityInspection.defect_quantity),
        ).group_by(QualityInspection.outcome)
    ).all()
    stats = {r[0]: {"inspections": r[1], "inspected": r[2] or ZERO, "defects": r[3] or ZERO} for r in rows}
    total_inspected = sum((s["inspected"] for s in stats.values()), ZERO)
    total_defects = sum((s["defects"] for s in stats.values()), ZERO)
    return {
        "inspections": sum(s["inspections"] for s in stats.values()),
        "passed": stats.get(InspectionOutcome.PASS, {}).get("inspections", 0),
        "failed": stats.get(InspectionOutcome.FAIL, {}).get("inspections", 0),
        "units_inspected": str(total_inspected),
        "defect_units": str(total_defects),
        "defect_rate": round(float(total_defects / total_inspected * 100), 2) if total_inspected else None,
    }


def report_fulfillment(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            CustomerOrder.order_number,
            CustomerOrder.status,
            CustomerOrder.required_date,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.delivered_quantity),
        )
        .join(OrderItem)
        .where(
            CustomerOrder.status.in_(
                [OrderStatus.CONFIRMED, OrderStatus.IN_PRODUCTION, OrderStatus.PARTIALLY_FULFILLED, OrderStatus.FULFILLED]
            )
        )
        .group_by(CustomerOrder.id)
        .order_by(CustomerOrder.required_date.asc().nulls_last())
    ).all()
    return [
        {
            "order_number": r[0],
            "status": r[1],
            "required_date": r[2],
            "ordered": str(r[3]),
            "delivered": str(r[4]),
            "percent": round(float(r[4] / r[3] * 100), 1) if r[3] else 0,
        }
        for r in rows
    ]
