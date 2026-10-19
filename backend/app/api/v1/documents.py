import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.deps import DB, require
from app.core.errors import BusinessRuleError
from app.models import User
from app.permissions.policy import P
from app.schemas.document import ApprovalIn, ApprovalOut, DocumentOut
from app.services import documents as svc

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: DB,
    q: str | None = None,
    status: str | None = None,
    doc_type: str | None = None,
    user: User = Depends(require(P.DOCUMENTS_READ)),
):
    """Only documents visible to the caller's role are returned. Drafts are visible to document managers only."""
    return svc.list_visible(db, user, q, status, doc_type)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload(
    db: DB,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    doc_type: str = Form(default="OTHER"),
    allowed_roles: str = Form(default="[]"),
    document_id: int | None = Form(default=None, description="Upload a new version of an existing document"),
    user: User = Depends(require(P.DOCUMENTS_UPLOAD)),
):
    """Upload PDF, TXT, Markdown or DOCX (max MAX_UPLOAD_MB). New uploads are DRAFT until approved."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    try:
        roles = json.loads(allowed_roles or "[]")
        if not isinstance(roles, list):
            raise ValueError
    except ValueError:
        raise BusinessRuleError("allowed_roles must be a JSON array of role names") from None
    return svc.upload(
        db,
        user,
        filename=file.filename or "",
        data=data,
        title=title,
        doc_type=doc_type,
        allowed_roles=roles,
        document_id=document_id,
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: DB, user: User = Depends(require(P.DOCUMENTS_READ))):
    return svc.get_visible(db, user, document_id)


@router.post("/{document_id}/approve", response_model=DocumentOut)
def approve(document_id: int, body: ApprovalIn, db: DB, user: User = Depends(require(P.DOCUMENTS_APPROVE))):
    """Approve a draft version. The previously approved version is archived (history is kept)."""
    return svc.approve(db, user, document_id, body.version_id, body.comment)


@router.post("/{document_id}/archive", response_model=DocumentOut)
def archive(document_id: int, body: ApprovalIn, db: DB, user: User = Depends(require(P.DOCUMENTS_APPROVE))):
    """Soft-delete: archived documents are kept but no longer used by the assistant."""
    return svc.archive(db, user, document_id, body.comment)


@router.get("/{document_id}/approvals", response_model=list[ApprovalOut])
def approvals(document_id: int, db: DB, user: User = Depends(require(P.DOCUMENTS_READ))):
    return svc.approvals(db, user, document_id)


@router.get("/{document_id}/download", response_class=Response, responses={200: {"content": {"application/octet-stream": {}}}})
def download(document_id: int, db: DB, version_id: int | None = None, user: User = Depends(require(P.DOCUMENTS_READ))):
    v, data = svc.download(db, user, document_id, version_id)
    return Response(
        content=data,
        media_type=v.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(v.source_filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
