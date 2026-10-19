"""Quality inspections.

PASS: (inspected - defects) become approved finished goods (stock PRODUCE); defects are QC-rejected.
FAIL: defects are QC-rejected and the rest goes ON HOLD; nothing is approved. A reinspection
      (after corrective action) of the held quantity creates a new linked record; the original
      record is never modified except for being flagged as reinspected.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, InvalidTransitionError
from app.models import ProductionJob, ProductionOutput, QualityInspection, User
from app.models.enums import InspectionOutcome, JobStatus
from app.schemas.quality import InspectionIn, ReinspectIn
from app.services import audit, inventory
from app.services.catalog import QUALITY_STAGE
from app.services.common import get_or_404, next_number, qty


def _check_job_at_qc(job: ProductionJob) -> None:
    if job.status != JobStatus.IN_PROGRESS:
        raise BusinessRuleError(f"Job {job.job_number} is {job.status}; only in-progress jobs can be inspected")
    if not job.current_stage or job.current_stage.stage_code != QUALITY_STAGE:
        raise BusinessRuleError(f"Job {job.job_number} has not reached the quality inspection stage")


def _apply_outcome(db: Session, user: User, job: ProductionJob, insp: QualityInspection) -> None:
    good = qty(insp.quantity_inspected - insp.defect_quantity)
    job.qc_rejected_quantity = qty(job.qc_rejected_quantity + insp.defect_quantity)
    if insp.outcome == InspectionOutcome.PASS:
        insp.approved_quantity = good
        job.approved_quantity = qty(job.approved_quantity + good)
        if good > 0:
            inventory.produce_finished(db, user, job, good, insp.inspection_number)
    else:
        insp.approved_quantity = Decimal("0")
        job.hold_quantity = qty(job.hold_quantity + good)


def create_inspection(db: Session, user: User, data: InspectionIn) -> QualityInspection:
    job = get_or_404(db, ProductionJob, data.production_job_id, "Job", lock=True)
    _check_job_at_qc(job)
    if data.quantity_inspected > job.pending_inspection_quantity:
        raise BusinessRuleError(
            f"Only {job.pending_inspection_quantity} units are awaiting inspection for {job.job_number}",
            {"pending": str(job.pending_inspection_quantity)},
        )
    if (
        data.batch_ref
        and not db.execute(
            select(ProductionOutput.id).where(ProductionOutput.job_id == job.id, ProductionOutput.batch_ref == data.batch_ref)
        ).first()
    ):
        raise BusinessRuleError(f"Batch {data.batch_ref} does not belong to {job.job_number}")
    insp = QualityInspection(
        inspection_number=next_number(db, "inspection_number_seq", "QI-"),
        production_job_id=job.id,
        batch_ref=data.batch_ref,
        inspector_id=user.id,
        quantity_inspected=data.quantity_inspected,
        defect_quantity=data.defect_quantity,
        checklist=[c.model_dump() for c in data.checklist],
        defect_description=data.defect_description,
        outcome=data.outcome,
        corrective_action=data.corrective_action,
        comments=data.comments,
    )
    db.add(insp)
    db.flush()
    _apply_outcome(db, user, job, insp)
    audit.record(
        db,
        user,
        f"quality.{data.outcome.lower()}",
        "quality_inspection",
        insp.id,
        f"{insp.inspection_number} on {job.job_number}: {data.outcome} "
        f"({data.quantity_inspected} inspected, {data.defect_quantity} defects)",
    )
    db.commit()
    return insp


def reinspect(db: Session, user: User, inspection_id: int, data: ReinspectIn) -> QualityInspection:
    original = get_or_404(db, QualityInspection, inspection_id, "Inspection", lock=True)
    if original.outcome != InspectionOutcome.FAIL:
        raise InvalidTransitionError("Only failed inspections can be reinspected")
    if original.reinspected:
        raise InvalidTransitionError(f"{original.inspection_number} has already been reinspected")
    job = get_or_404(db, ProductionJob, original.production_job_id, "Job", lock=True)
    _check_job_at_qc(job)
    held = qty(original.quantity_inspected - original.defect_quantity)
    if held <= 0:
        raise BusinessRuleError("Nothing is on hold from this inspection")
    if data.defect_quantity > held:
        raise BusinessRuleError(f"defect_quantity cannot exceed the reinspected quantity {held}")
    if data.defect_quantity > 0 and not data.defect_description:
        raise BusinessRuleError("defect_description is required when defects are recorded")
    job.hold_quantity = qty(job.hold_quantity - held)
    insp = QualityInspection(
        inspection_number=next_number(db, "inspection_number_seq", "QI-"),
        production_job_id=job.id,
        parent_id=original.id,
        batch_ref=original.batch_ref,
        inspector_id=user.id,
        quantity_inspected=held,
        defect_quantity=data.defect_quantity,
        checklist=[c.model_dump() for c in data.checklist],
        defect_description=data.defect_description,
        outcome=data.outcome,
        corrective_action=data.corrective_action,
        comments=data.comments,
    )
    db.add(insp)
    db.flush()
    original.reinspected = True
    _apply_outcome(db, user, job, insp)
    audit.record(
        db,
        user,
        f"quality.reinspect_{data.outcome.lower()}",
        "quality_inspection",
        insp.id,
        f"{insp.inspection_number} reinspection of {original.inspection_number}: {data.outcome}",
    )
    db.commit()
    return insp


def inspection_stmt(job_id: int | None, outcome: str | None, order_id: int | None, q: str | None):
    stmt = select(QualityInspection).join(ProductionJob, QualityInspection.production_job_id == ProductionJob.id)
    if job_id:
        stmt = stmt.where(QualityInspection.production_job_id == job_id)
    if outcome:
        stmt = stmt.where(QualityInspection.outcome == outcome)
    if order_id:
        stmt = stmt.where(ProductionJob.order_id == order_id)
    if q:
        stmt = stmt.where(QualityInspection.inspection_number.ilike(f"%{q}%") | ProductionJob.job_number.ilike(f"%{q}%"))
    return stmt.order_by(QualityInspection.id.desc())


def to_out(insp: QualityInspection) -> dict:
    from app.schemas.quality import InspectionOut

    d = InspectionOut.model_validate(insp).model_dump()
    d["order_number"] = insp.job.order.order_number if insp.job and insp.job.order else None
    return d
