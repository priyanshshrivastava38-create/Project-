"""Production jobs: creation from order lines, stage progression, output and completion."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, InvalidTransitionError
from app.models import CustomerOrder, OrderItem, ProductionJob, ProductionOutput, User, Warehouse
from app.models.enums import JobStatus, OrderStatus, StageStatus
from app.models.production import JobStage
from app.schemas.production import JobCreate, JobUpdate, OutputIn
from app.services import audit, inventory, orders
from app.services.catalog import QUALITY_STAGE
from app.services.common import get_or_404, next_number, qty

ZERO = Decimal("0")
OPEN_JOB = (JobStatus.PLANNED, JobStatus.IN_PROGRESS, JobStatus.ON_HOLD)


def is_overdue(job: ProductionJob, today: date | None = None) -> bool:
    return job.status in OPEN_JOB and job.target_date is not None and job.target_date < (today or date.today())


def default_output_warehouse(db: Session) -> Warehouse:
    wh = db.execute(select(Warehouse).where(Warehouse.code == "FG", Warehouse.is_active.is_(True))).scalar_one_or_none()
    wh = wh or db.execute(select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.id)).scalars().first()
    if wh is None:
        raise BusinessRuleError("No active warehouse configured")
    return wh


def create_job(db: Session, user: User, data: JobCreate) -> ProductionJob:
    item = get_or_404(db, OrderItem, data.order_item_id, "Order item")
    order = get_or_404(db, CustomerOrder, item.order_id, "Order", lock=True)
    if order.status not in (OrderStatus.CONFIRMED, OrderStatus.IN_PRODUCTION, OrderStatus.PARTIALLY_FULFILLED):
        raise BusinessRuleError(f"Jobs can only be created for confirmed orders (order is {order.status})")
    already = db.execute(
        select(func.coalesce(func.sum(ProductionJob.planned_quantity), 0)).where(
            ProductionJob.order_item_id == item.id, ProductionJob.status != JobStatus.CANCELLED
        )
    ).scalar_one()
    remaining = item.quantity - already
    if remaining <= 0:
        raise BusinessRuleError(f"Line {item.line_number} is already fully planned")
    planned = data.planned_quantity or remaining
    if planned > remaining:
        raise BusinessRuleError(f"Planned quantity {planned} exceeds the unplanned remainder {remaining}")
    product = item.product
    if not product.route:
        raise BusinessRuleError(f"Product {product.sku} has no production route configured")
    if data.output_warehouse_id:
        wh = get_or_404(db, Warehouse, data.output_warehouse_id, "Warehouse")
    else:
        wh = default_output_warehouse(db)
    job = ProductionJob(
        job_number=next_number(db, "job_number_seq", "JOB-"),
        order_id=order.id,
        order_item_id=item.id,
        product_id=product.id,
        planned_quantity=planned,
        start_date=data.start_date,
        target_date=data.target_date or order.required_date,
        priority=data.priority,
        assigned_to=data.assigned_to,
        output_warehouse_id=wh.id,
        notes=data.notes,
        created_by_id=user.id,
        status=JobStatus.PLANNED,
        current_stage_seq=1,
    )
    job.stages = [JobStage(sequence=s.sequence, stage_code=s.stage.code, stage_name=s.stage.name) for s in product.route]
    db.add(job)
    db.flush()
    orders.mark_in_production(db, order, user)
    audit.record(
        db,
        user,
        "production.create_job",
        "production_job",
        job.id,
        f"Created {job.job_number} for {order.order_number} line {item.line_number} ({planned} {product.uom})",
    )
    db.commit()
    return job


def update_job(db: Session, user: User, job_id: int, data: JobUpdate) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
        raise BusinessRuleError(f"Job is {job.status}")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(job, k, v)
    audit.record(
        db, user, "production.update_job", "production_job", job.id, f"Updated {job.job_number}", {"fields": sorted(changes)}
    )
    db.commit()
    return job


def allocate(db: Session, user: User, job_id: int, warehouse_id: int | None) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    inventory.auto_allocate(db, user, job, warehouse_id)
    db.commit()
    return job


def start_job(db: Session, user: User, job_id: int) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status != JobStatus.PLANNED:
        raise InvalidTransitionError(f"Only PLANNED jobs can be started (job is {job.status})")
    if not inventory.materials_ready(db, job):
        raise BusinessRuleError("Required materials are not fully allocated to this job", {"materials": material_status(db, job)})
    now = datetime.now(UTC)
    job.status = JobStatus.IN_PROGRESS
    job.started_at = now
    job.start_date = job.start_date or now.date()
    first = job.stages[0]
    first.status, first.started_at = StageStatus.IN_PROGRESS, now
    job.current_stage_seq = first.sequence
    audit.record(db, user, "production.start", "production_job", job.id, f"Started {job.job_number} at {first.stage_name}")
    db.commit()
    return job


def advance_stage(db: Session, user: User, job_id: int, notes: str | None) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status != JobStatus.IN_PROGRESS:
        raise InvalidTransitionError(f"Job must be IN_PROGRESS to advance (job is {job.status})")
    current = job.current_stage
    nxt = next((s for s in job.stages if s.sequence > current.sequence), None)
    if nxt is None:
        raise InvalidTransitionError("Job is at its final stage; record inspections and complete the job instead")
    if nxt.stage_code == QUALITY_STAGE and job.produced_quantity <= 0:
        raise BusinessRuleError("Record production output before moving the job to quality inspection")
    now = datetime.now(UTC)
    current.status, current.completed_at, current.completed_by_id = StageStatus.DONE, now, user.id
    if notes:
        current.notes = notes
    nxt.status, nxt.started_at = StageStatus.IN_PROGRESS, now
    job.current_stage_seq = nxt.sequence
    audit.record(
        db, user, "production.advance", "production_job", job.id, f"{job.job_number}: {current.stage_name} -> {nxt.stage_name}"
    )
    db.commit()
    return job


def record_output(db: Session, user: User, job_id: int, data: OutputIn) -> ProductionOutput:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status != JobStatus.IN_PROGRESS:
        raise InvalidTransitionError(f"Output can only be recorded for IN_PROGRESS jobs (job is {job.status})")
    good_outstanding = job.produced_quantity - job.qc_rejected_quantity  # approved + pending + on hold
    if good_outstanding + data.good_quantity > job.planned_quantity:
        raise BusinessRuleError(
            f"Good output would exceed the planned quantity ({job.planned_quantity}); "
            f"at most {job.planned_quantity - good_outstanding} more units can be reported"
        )
    batch_ref = next_number(db, "batch_number_seq", f"{job.job_number}-B", 3)
    inventory.consume_for_job(db, user, job, data.good_quantity + data.scrap_quantity, batch_ref)
    out = ProductionOutput(
        job_id=job.id,
        batch_ref=batch_ref,
        good_quantity=data.good_quantity,
        scrap_quantity=data.scrap_quantity,
        notes=data.notes,
        recorded_by_id=user.id,
    )
    db.add(out)
    job.produced_quantity = qty(job.produced_quantity + data.good_quantity)
    job.scrap_quantity = qty(job.scrap_quantity + data.scrap_quantity)
    db.flush()
    audit.record(
        db,
        user,
        "production.output",
        "production_job",
        job.id,
        f"{job.job_number} batch {batch_ref}: {data.good_quantity} good, {data.scrap_quantity} scrap",
    )
    db.commit()
    return out


def complete_job(db: Session, user: User, job_id: int) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status != JobStatus.IN_PROGRESS:
        raise InvalidTransitionError(f"Only IN_PROGRESS jobs can be completed (job is {job.status})")
    last = job.stages[-1]
    problems = []
    if job.current_stage_seq != last.sequence:
        problems.append(f"job must be at its final stage ({last.stage_name})")
    if job.pending_inspection_quantity > 0:
        problems.append(f"{job.pending_inspection_quantity} units are awaiting inspection")
    if job.hold_quantity > 0:
        problems.append(f"{job.hold_quantity} units are on hold after a failed inspection")
    if job.approved_quantity < job.planned_quantity:
        problems.append(f"only {job.approved_quantity} of {job.planned_quantity} units have passed inspection")
    if problems:
        raise BusinessRuleError("Job cannot be completed: " + "; ".join(problems), {"problems": problems})
    now = datetime.now(UTC)
    last.status, last.completed_at, last.completed_by_id = StageStatus.DONE, now, user.id
    job.status = JobStatus.COMPLETED
    job.actual_completion_at = now
    inventory.release_all_for_job(db, user, job, f"{job.job_number} completed; returning unused material")
    audit.record(db, user, "production.complete", "production_job", job.id, f"Completed {job.job_number}")
    db.commit()
    return job


def cancel_job(db: Session, user: User, job_id: int, reason: str) -> ProductionJob:
    job = get_or_404(db, ProductionJob, job_id, "Job", lock=True)
    if job.status not in (JobStatus.PLANNED, JobStatus.IN_PROGRESS):
        raise InvalidTransitionError(f"Job is {job.status}")
    if job.produced_quantity > 0 or job.scrap_quantity > 0:
        raise BusinessRuleError("Output has already been recorded for this job; it cannot be cancelled")
    inventory.release_all_for_job(db, user, job, f"{job.job_number} cancelled")
    job.status = JobStatus.CANCELLED
    audit.record(db, user, "production.cancel", "production_job", job.id, f"Cancelled {job.job_number}: {reason}")
    db.commit()
    return job


def material_status(db: Session, job: ProductionJob) -> list[dict]:
    held = inventory.material_held_by_job(db, job.id)
    totals = inventory.material_totals(db)
    outstanding = inventory.outstanding_requirements(job)
    out = []
    for pm in job.product.materials:
        need = qty(pm.quantity_per_unit * job.planned_quantity)
        h = held.get(pm.material_id, {"allocated": ZERO, "consumed": ZERO})
        open_job = job.status in (JobStatus.PLANNED, JobStatus.IN_PROGRESS)
        out.append(
            {
                "material_id": pm.material_id,
                "sku": pm.material.sku,
                "name": pm.material.name,
                "uom": pm.material.uom,
                "required": need,
                "allocated": h["allocated"],
                "consumed": h["consumed"],
                "shortfall": max(ZERO, outstanding[pm.material_id] - h["allocated"]) if open_job else ZERO,
                "available_in_stock": totals.get(pm.material_id, ZERO),
            }
        )
    return out


def summary(job: ProductionJob) -> dict:
    from app.schemas.production import JobSummary

    d = JobSummary.model_validate(job).model_dump()
    d["is_overdue"] = is_overdue(job)
    return d


def job_detail(db: Session, job_id: int) -> dict:
    from app.schemas.production import JobStageOut, OutputOut

    job = get_or_404(db, ProductionJob, job_id, "Job")
    d = summary(job)
    d.update(
        {
            "scrap_quantity": job.scrap_quantity,
            "qc_rejected_quantity": job.qc_rejected_quantity,
            "started_at": job.started_at,
            "notes": job.notes,
            "output_warehouse_id": job.output_warehouse_id,
            "created_at": job.created_at,
            "stages": [JobStageOut.model_validate(s) for s in job.stages],
            "outputs": [OutputOut.model_validate(o) for o in job.outputs],
            "materials": material_status(db, job),
            "reservations": [inventory.reservation_dict(r) for r in inventory.job_reservations(db, job.id)],
            "materials_ready": inventory.materials_ready(db, job),
        }
    )
    return d


def job_stmt(status: str | None, stage: str | None, order_id: int | None, overdue: bool | None, q: str | None):
    stmt = select(ProductionJob).join(CustomerOrder, ProductionJob.order_id == CustomerOrder.id)
    if status:
        stmt = stmt.where(ProductionJob.status.in_(status.split(",")))
    if order_id:
        stmt = stmt.where(ProductionJob.order_id == order_id)
    if stage:
        stmt = stmt.join(
            JobStage, (JobStage.job_id == ProductionJob.id) & (JobStage.sequence == ProductionJob.current_stage_seq)
        ).where(JobStage.stage_code == stage, ProductionJob.status == JobStatus.IN_PROGRESS)
    if overdue:
        stmt = stmt.where(ProductionJob.status.in_(OPEN_JOB), ProductionJob.target_date < date.today())
    if q:
        stmt = stmt.where(or_(ProductionJob.job_number.ilike(f"%{q}%"), CustomerOrder.order_number.ilike(f"%{q}%")))
    return stmt.order_by(ProductionJob.target_date.asc().nulls_last(), ProductionJob.id)


def board(db: Session) -> list[dict]:
    """Jobs grouped into PLANNED, each route stage (in-progress jobs) and recently COMPLETED."""
    from app.models import StageDefinition

    jobs = list(
        db.execute(
            select(ProductionJob).where(ProductionJob.status.in_(OPEN_JOB)).order_by(ProductionJob.target_date.asc().nulls_last())
        )
        .unique()
        .scalars()
    )
    done = list(
        db.execute(
            select(ProductionJob)
            .where(ProductionJob.status == JobStatus.COMPLETED)
            .order_by(ProductionJob.actual_completion_at.desc())
            .limit(20)
        )
        .unique()
        .scalars()
    )
    stage_defs = list(
        db.execute(select(StageDefinition).where(StageDefinition.is_active.is_(True)).order_by(StageDefinition.id)).scalars()
    )
    columns = [{"key": "PLANNED", "title": "Planned", "jobs": []}]
    columns += [{"key": s.code, "title": s.name, "jobs": []} for s in stage_defs]
    index = {c["key"]: c for c in columns}
    for j in jobs:
        key = "PLANNED" if j.status == JobStatus.PLANNED else (j.current_stage.stage_code if j.current_stage else "PLANNED")
        index.setdefault(key, {"key": key, "title": key.title(), "jobs": []})["jobs"].append(summary(j))
        if key not in [c["key"] for c in columns]:
            columns.append(index[key])
    columns.append({"key": "COMPLETED", "title": "Completed", "jobs": [summary(j) for j in done]})
    return columns
