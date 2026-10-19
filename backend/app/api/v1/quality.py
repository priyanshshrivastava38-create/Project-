from fastapi import APIRouter, Depends

from app.core.deps import DB, require
from app.models import QualityInspection, User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.quality import InspectionIn, InspectionOut, ReinspectIn
from app.services import quality as svc
from app.services.common import get_or_404, paginate

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/inspections", response_model=Page[InspectionOut])
def list_inspections(
    db: DB,
    pp: PageParams = Depends(),
    job_id: int | None = None,
    outcome: str | None = None,
    order_id: int | None = None,
    q: str | None = None,
    _: User = Depends(require(P.QUALITY_READ)),
) -> dict:
    items, total = paginate(db, svc.inspection_stmt(job_id, outcome, order_id, q), pp.page, pp.page_size)
    return {"items": [svc.to_out(i) for i in items], "total": total, "page": pp.page, "page_size": pp.page_size}


@router.get("/inspections/{inspection_id}", response_model=InspectionOut)
def get_inspection(inspection_id: int, db: DB, _: User = Depends(require(P.QUALITY_READ))):
    return svc.to_out(get_or_404(db, QualityInspection, inspection_id, "Inspection"))


@router.post("/inspections", response_model=InspectionOut, status_code=201)
def create_inspection(body: InspectionIn, db: DB, user: User = Depends(require(P.QUALITY_WRITE))):
    """PASS approves (inspected − defects) units into finished goods. FAIL approves nothing and holds the good units for reinspection."""
    return svc.to_out(svc.create_inspection(db, user, body))


@router.post("/inspections/{inspection_id}/reinspect", response_model=InspectionOut, status_code=201)
def reinspect(inspection_id: int, body: ReinspectIn, db: DB, user: User = Depends(require(P.QUALITY_WRITE))):
    return svc.to_out(svc.reinspect(db, user, inspection_id, body))
