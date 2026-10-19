"""Permission-checked, read-only business data lookups used by the assistant.

Each tool declares the permission it needs; the assistant refuses if the user's role lacks it.
Results are plain facts (label/value) plus a deterministic natural-language answer.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CustomerOrder, Delivery, ProductionJob
from app.models.enums import DeliveryStatus, JobStatus
from app.permissions.policy import P
from app.services import inventory, orders, production
from app.services.catalog import QUALITY_STAGE


@dataclass
class ToolResult:
    answer: str
    facts: list[tuple[str, str]] = field(default_factory=list)
    found: bool = True


def _n(v) -> str:
    s = format(v, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def order_status(db: Session, order_number: str) -> ToolResult:
    order = (
        db.execute(select(CustomerOrder).where(CustomerOrder.order_number == order_number.upper())).unique().scalar_one_or_none()
    )
    if order is None:
        return ToolResult(f"I could not find order {order_number.upper()} in the system.", found=False)
    progress = orders.line_progress(db, order)
    lines = []
    facts = [
        ("Order", order.order_number),
        ("Customer", order.customer.company_name),
        ("Status", order.status),
        ("Order date", order.order_date.isoformat()),
        ("Required date", order.required_date.isoformat() if order.required_date else "not set"),
        ("Total", f"{order.currency} {_n(order.total)}"),
    ]
    for it in order.items:
        p = progress[it.id]
        lines.append(
            f"{it.sku} ({it.description}): ordered {_n(it.quantity)}, planned {_n(p['planned_quantity'])}, "
            f"QC-approved {_n(p['approved_quantity'])}, delivered {_n(it.delivered_quantity)}"
        )
        facts.append(
            (
                f"Line {it.line_number} {it.sku}",
                f"ordered {_n(it.quantity)} / approved {_n(p['approved_quantity'])} / delivered {_n(it.delivered_quantity)}",
            )
        )
    jobs = db.execute(select(ProductionJob).where(ProductionJob.order_id == order.id)).unique().scalars().all()
    job_txt = (
        ", ".join(
            f"{j.job_number} {j.status}"
            + (f" at {j.current_stage.stage_name}" if j.status == JobStatus.IN_PROGRESS and j.current_stage else "")
            for j in jobs
        )
        or "none"
    )
    facts.append(("Production jobs", job_txt))
    answer = (
        f"Order {order.order_number} for {order.customer.company_name} is {order.status}. "
        f"Total {order.currency} {_n(order.total)}, required by {order.required_date or 'no date set'}. "
        f"Lines: " + "; ".join(lines) + f". Production jobs: {job_txt}."
    )
    return ToolResult(answer, facts)


def job_status(db: Session, job_number: str) -> ToolResult:
    job = db.execute(select(ProductionJob).where(ProductionJob.job_number == job_number.upper())).unique().scalar_one_or_none()
    if job is None:
        return ToolResult(f"I could not find production job {job_number.upper()}.", found=False)
    stage = job.current_stage.stage_name if job.current_stage else "-"
    answer = (
        f"{job.job_number} ({job.product.sku}) for {job.order.order_number} is {job.status}"
        + (f" at stage {stage}" if job.status == JobStatus.IN_PROGRESS else "")
        + f". Planned {_n(job.planned_quantity)}, produced {_n(job.produced_quantity)}, QC-approved "
        f"{_n(job.approved_quantity)}, rejected {_n(job.rejected_quantity)}. Target date {job.target_date or 'not set'}"
        + (" — OVERDUE." if production.is_overdue(job) else ".")
    )
    return ToolResult(
        answer,
        [
            ("Job", job.job_number),
            ("Status", job.status),
            ("Stage", stage),
            ("Planned", _n(job.planned_quantity)),
            ("Approved", _n(job.approved_quantity)),
        ],
    )


def low_stock(db: Session) -> ToolResult:
    items = inventory.low_stock_materials(db)
    if not items:
        return ToolResult("No active materials are below their reorder level.", [("Low-stock materials", "0")])
    facts = [
        (f"{i['sku']} {i['name']}", f"available {_n(i['available'])} {i['uom']} / reorder level {_n(i['reorder_level'])}")
        for i in items
    ]
    answer = (
        f"{len(items)} material(s) are below their reorder level: "
        + "; ".join(
            f"{i['sku']} ({i['name']}) has {_n(i['available'])} {i['uom']} available vs reorder level {_n(i['reorder_level'])}"
            for i in items
        )
        + "."
    )
    return ToolResult(answer, facts)


def overdue_jobs(db: Session) -> ToolResult:
    jobs = (
        db.execute(
            select(ProductionJob)
            .where(ProductionJob.status.in_(production.OPEN_JOB), ProductionJob.target_date < date.today())
            .order_by(ProductionJob.target_date)
        )
        .unique()
        .scalars()
        .all()
    )
    if not jobs:
        return ToolResult("No open production jobs are past their target date.", [("Overdue jobs", "0")])
    facts = [(j.job_number, f"{j.order.order_number} · {j.product.sku} · target {j.target_date} · {j.status}") for j in jobs]
    answer = (
        f"{len(jobs)} production job(s) are overdue: "
        + "; ".join(
            f"{j.job_number} for {j.order.order_number} ({j.product.sku}), target {j.target_date}, status {j.status}"
            for j in jobs
        )
        + "."
    )
    return ToolResult(answer, facts)


def awaiting_inspection(db: Session) -> ToolResult:
    jobs = db.execute(select(ProductionJob).where(ProductionJob.status == JobStatus.IN_PROGRESS)).unique().scalars().all()
    waiting = [
        j
        for j in jobs
        if j.current_stage
        and j.current_stage.stage_code == QUALITY_STAGE
        and (j.pending_inspection_quantity > 0 or j.hold_quantity > 0)
    ]
    if not waiting:
        return ToolResult("No orders currently have output waiting for quality inspection.", [("Waiting for QC", "0")])
    facts = [
        (j.order.order_number, f"{j.job_number}: {_n(j.pending_inspection_quantity)} pending, {_n(j.hold_quantity)} on hold")
        for j in waiting
    ]
    answer = (
        "Orders waiting for quality inspection: "
        + "; ".join(
            f"{j.order.order_number} via {j.job_number} ({_n(j.pending_inspection_quantity)} units pending inspection"
            + (f", {_n(j.hold_quantity)} on hold for reinspection" if j.hold_quantity > 0 else "")
            + ")"
            for j in waiting
        )
        + "."
    )
    return ToolResult(answer, facts)


def ready_for_dispatch(db: Session) -> ToolResult:
    from app.services.deliveries import dispatchable_orders

    ready = dispatchable_orders(db)
    transit = (
        db.execute(select(Delivery).where(Delivery.status.in_([DeliveryStatus.DISPATCHED, DeliveryStatus.IN_TRANSIT])))
        .unique()
        .scalars()
        .all()
    )
    facts = [(o["order_number"], ", ".join(f"{ln['sku']} {_n(ln['dispatchable'])}" for ln in o["lines"])) for o in ready]
    facts += [
        (d.delivery_number, f"{d.status} · {d.order.order_number} · {d.carrier or ''} {d.tracking_number or ''}".strip())
        for d in transit
    ]
    parts = []
    parts.append(
        (
            "Orders with QC-approved goods ready to schedule for dispatch: "
            + "; ".join(f"{o['order_number']} ({o['customer_name']})" for o in ready)
        )
        if ready
        else "No orders have unallocated QC-approved goods ready for dispatch"
    )
    parts.append(f"{len(transit)} deliver{'y is' if len(transit) == 1 else 'ies are'} dispatched or in transit")
    return ToolResult(". ".join(parts) + ".", facts)


TOOLS = {
    "order_status": (P.ORDERS_READ, "orders", lambda db, p: order_status(db, p["order_number"])),
    "job_status": (P.PRODUCTION_READ, "production", lambda db, p: job_status(db, p["job_number"])),
    "low_stock": (P.INVENTORY_READ, "inventory", lambda db, p: low_stock(db)),
    "overdue_jobs": (P.PRODUCTION_READ, "production", lambda db, p: overdue_jobs(db)),
    "awaiting_inspection": (P.PRODUCTION_READ, "production", lambda db, p: awaiting_inspection(db)),
    "ready_for_dispatch": (P.DELIVERIES_READ, "delivery", lambda db, p: ready_for_dispatch(db)),
}
