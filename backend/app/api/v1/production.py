from fastapi import APIRouter, Depends

from app.core.deps import DB, require
from app.models import User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.order import StatusChange
from app.schemas.production import AdvanceIn, AllocateIn, JobCreate, JobDetail, JobSummary, JobUpdate, OutputIn, OutputOut
from app.services import production as svc
from app.services.common import paginate

router = APIRouter(prefix="/production", tags=["production"])


@router.get("/jobs", response_model=Page[JobSummary])
def list_jobs(
    db: DB,
    pp: PageParams = Depends(),
    status: str | None = None,
    stage: str | None = None,
    order_id: int | None = None,
    overdue: bool | None = None,
    q: str | None = None,
    _: User = Depends(require(P.PRODUCTION_READ)),
) -> dict:
    items, total = paginate(db, svc.job_stmt(status, stage, order_id, overdue, q), pp.page, pp.page_size)
    return {"items": [svc.summary(j) for j in items], "total": total, "page": pp.page, "page_size": pp.page_size}


@router.get("/board")
def board(db: DB, _: User = Depends(require(P.PRODUCTION_READ))) -> list[dict]:
    """Open jobs grouped by stage, plus the 20 most recently completed."""
    return [
        {**c, "jobs": [JobSummary.model_validate(j).model_dump(mode="json") | {"is_overdue": j["is_overdue"]} for j in c["jobs"]]}
        for c in svc.board(db)
    ]


@router.post("/jobs", response_model=JobDetail, status_code=201)
def create_job(body: JobCreate, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    job = svc.create_job(db, user, body)
    return svc.job_detail(db, job.id)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: DB, _: User = Depends(require(P.PRODUCTION_READ))):
    return svc.job_detail(db, job_id)


@router.patch("/jobs/{job_id}", response_model=JobDetail)
def update_job(job_id: int, body: JobUpdate, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    svc.update_job(db, user, job_id, body)
    return svc.job_detail(db, job_id)


@router.post("/jobs/{job_id}/allocate-materials", response_model=JobDetail)
def allocate(job_id: int, body: AllocateIn, db: DB, user: User = Depends(require(P.INVENTORY_RESERVE))):
    """Reserve every outstanding material requirement (all-or-nothing). Fails with the shortages if stock is insufficient."""
    svc.allocate(db, user, job_id, body.warehouse_id)
    return svc.job_detail(db, job_id)


@router.post("/jobs/{job_id}/start", response_model=JobDetail)
def start(job_id: int, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    svc.start_job(db, user, job_id)
    return svc.job_detail(db, job_id)


@router.post("/jobs/{job_id}/advance", response_model=JobDetail)
def advance(job_id: int, body: AdvanceIn, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    """Move to the next stage of the job's route. Stages cannot be skipped."""
    svc.advance_stage(db, user, job_id, body.notes)
    return svc.job_detail(db, job_id)


@router.post("/jobs/{job_id}/record-output", response_model=OutputOut, status_code=201)
def record_output(job_id: int, body: OutputIn, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    """Report a batch of good and scrapped units; consumes allocated material for both."""
    return svc.record_output(db, user, job_id, body)


@router.post("/jobs/{job_id}/complete", response_model=JobDetail)
def complete(job_id: int, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    svc.complete_job(db, user, job_id)
    return svc.job_detail(db, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobDetail)
def cancel(job_id: int, body: StatusChange, db: DB, user: User = Depends(require(P.PRODUCTION_WRITE))):
    svc.cancel_job(db, user, job_id, body.reason)
    return svc.job_detail(db, job_id)
