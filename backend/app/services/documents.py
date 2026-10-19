"""Business document library: upload, versioning, approval, visibility and download."""

import hashlib
import logging
import os
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Document, DocumentApproval, DocumentChunk, DocumentFile, DocumentVersion, User
from app.models.enums import DocumentStatus
from app.permissions.policy import P, Role, has_permission
from app.services import audit
from app.services.common import get_or_404
from app.services.extraction import extract

logger = logging.getLogger("metalflow.documents")

ALLOWED = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
DOC_TYPES = {"PROCEDURE", "SPECIFICATION", "POLICY", "WORK_INSTRUCTION", "QUALITY_STANDARD", "CONTRACT", "OTHER"}


def can_view(user: User, doc: Document) -> bool:
    if user.role == Role.ADMIN:
        return True
    if doc.allowed_roles and user.role not in doc.allowed_roles:
        return False
    if doc.status == DocumentStatus.APPROVED:
        return True
    # Drafts/archived documents are visible only to people who manage documents.
    return has_permission(user.role, P.DOCUMENTS_UPLOAD) or has_permission(user.role, P.DOCUMENTS_APPROVE)


def get_visible(db: Session, user: User, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    # 404 rather than 403 so restricted document IDs cannot be probed.
    if doc is None or not can_view(user, doc):
        raise NotFoundError(f"Document {document_id} not found")
    return doc


def _validate_file(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED:
        raise BusinessRuleError(f"Unsupported file type '{ext or 'none'}'", {"allowed": sorted(ALLOWED)})
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(data) == 0:
        raise BusinessRuleError("The uploaded file is empty")
    if len(data) > max_bytes:
        raise BusinessRuleError(f"File exceeds the {get_settings().max_upload_mb} MB limit")
    # Content sniffing: the extension must match the actual bytes.
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise BusinessRuleError("File content is not a valid PDF")
    if ext == ".docx" and not data.startswith(b"PK\x03\x04"):
        raise BusinessRuleError("File content is not a valid DOCX")
    if ext in (".txt", ".md", ".markdown"):
        if b"\x00" in data[:4096]:
            raise BusinessRuleError("Text files must not contain binary data")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise BusinessRuleError("Text files must be UTF-8 encoded") from None
    return ext


def upload(
    db: Session,
    user: User,
    *,
    filename: str,
    data: bytes,
    title: str | None,
    doc_type: str,
    allowed_roles: list[str],
    document_id: int | None,
) -> Document:
    ext = _validate_file(filename, data)
    if doc_type not in DOC_TYPES:
        raise BusinessRuleError("Unknown document type", {"allowed": sorted(DOC_TYPES)})
    roles = sorted(set(allowed_roles))
    for r in roles:
        if r not in Role.__members__:
            raise BusinessRuleError(f"Unknown role '{r}'")
    digest = hashlib.sha256(data).hexdigest()
    if document_id:
        doc = get_or_404(db, Document, document_id, "Document", lock=True)
        if not can_view(user, doc):
            raise NotFoundError(f"Document {document_id} not found")
        if any(v.content_hash == digest for v in doc.versions):
            raise ConflictError("This exact file is already a version of the document")
        version_number = max(v.version_number for v in doc.versions) + 1
    else:
        if not title or len(title.strip()) < 3:
            raise BusinessRuleError("A title (min 3 characters) is required for a new document")
        doc = Document(
            title=title.strip()[:200], doc_type=doc_type, allowed_roles=roles, created_by_id=user.id, status=DocumentStatus.DRAFT
        )
        db.add(doc)
        db.flush()
        version_number = 1
    try:
        ex = extract(data, ext)
    except Exception as e:  # malformed file: reject rather than store something unsearchable silently
        logger.warning("Extraction failed for %s: %s", filename, type(e).__name__)
        raise BusinessRuleError("Could not read the document; the file may be corrupt or password-protected") from None
    v = DocumentVersion(
        document_id=doc.id,
        version_number=version_number,
        status=DocumentStatus.DRAFT,
        source_filename=os.path.basename(filename)[:255],
        content_type=ALLOWED[ext],
        size_bytes=len(data),
        content_hash=digest,
        page_count=ex.page_count,
        extraction_note=ex.note,
        uploaded_by_id=user.id,
    )
    db.add(v)
    db.flush()
    db.add(DocumentFile(version_id=v.id, data=data))
    for i, c in enumerate(ex.chunks):
        db.add(DocumentChunk(version_id=v.id, chunk_index=i, page_number=c.page_number, section=c.section, text=c.text))
    if doc.status == DocumentStatus.ARCHIVED:
        doc.status = DocumentStatus.DRAFT
    audit.record(
        db,
        user,
        "document.upload",
        "document",
        doc.id,
        f"Uploaded v{version_number} of '{doc.title}' ({len(ex.chunks)} text chunks)",
    )
    db.commit()
    db.refresh(doc)
    return doc


def approve(db: Session, user: User, document_id: int, version_id: int | None, comment: str | None) -> Document:
    doc = get_or_404(db, Document, document_id, "Document", lock=True)
    drafts = [v for v in doc.versions if v.status == DocumentStatus.DRAFT]
    if version_id:
        v = next((x for x in doc.versions if x.id == version_id), None)
        if v is None:
            raise NotFoundError("Version not found on this document")
    elif drafts:
        v = drafts[-1]
    else:
        raise BusinessRuleError("There is no draft version to approve")
    if v.status != DocumentStatus.DRAFT:
        raise BusinessRuleError(f"Version {v.version_number} is {v.status}; only drafts can be approved")
    now = datetime.now(UTC)
    for other in doc.versions:  # one authoritative version at a time; history is kept
        if other.status == DocumentStatus.APPROVED:
            other.status = DocumentStatus.ARCHIVED
            db.add(
                DocumentApproval(
                    version_id=other.id, action="ARCHIVED", comment=f"Superseded by v{v.version_number}", user_id=user.id
                )
            )
    v.status, v.approved_by_id, v.approved_at = DocumentStatus.APPROVED, user.id, now
    doc.status = DocumentStatus.APPROVED
    db.add(DocumentApproval(version_id=v.id, action="APPROVED", comment=comment, user_id=user.id))
    audit.record(db, user, "document.approve", "document", doc.id, f"Approved v{v.version_number} of '{doc.title}'")
    db.commit()
    db.refresh(doc)
    return doc


def archive(db: Session, user: User, document_id: int, comment: str | None) -> Document:
    doc = get_or_404(db, Document, document_id, "Document", lock=True)
    if doc.status == DocumentStatus.ARCHIVED:
        raise BusinessRuleError("Document is already archived")
    for v in doc.versions:
        if v.status != DocumentStatus.ARCHIVED:
            v.status = DocumentStatus.ARCHIVED
            db.add(DocumentApproval(version_id=v.id, action="ARCHIVED", comment=comment, user_id=user.id))
    doc.status = DocumentStatus.ARCHIVED
    audit.record(db, user, "document.archive", "document", doc.id, f"Archived '{doc.title}'")
    db.commit()
    db.refresh(doc)
    return doc


def download(db: Session, user: User, document_id: int, version_id: int | None) -> tuple[DocumentVersion, bytes]:
    doc = get_visible(db, user, document_id)
    if version_id:
        v = next((x for x in doc.versions if x.id == version_id), None)
    else:
        v = next((x for x in reversed(doc.versions) if x.status == DocumentStatus.APPROVED), None) or doc.versions[-1]
    if v is None:
        raise NotFoundError("Version not found")
    if v.status != DocumentStatus.APPROVED and not (
        has_permission(user.role, P.DOCUMENTS_UPLOAD) or has_permission(user.role, P.DOCUMENTS_APPROVE)
    ):
        raise NotFoundError("Version not found")
    f = db.get(DocumentFile, v.id)
    audit.record(db, user, "document.download", "document", doc.id, f"Downloaded v{v.version_number} of '{doc.title}'")
    db.commit()
    return v, f.data


def approvals(db: Session, user: User, document_id: int) -> list[DocumentApproval]:
    doc = get_visible(db, user, document_id)
    ids = [v.id for v in doc.versions]
    return list(
        db.execute(select(DocumentApproval).where(DocumentApproval.version_id.in_(ids)).order_by(DocumentApproval.id))
        .unique()
        .scalars()
    )


def list_visible(db: Session, user: User, q: str | None, status: str | None, doc_type: str | None) -> list[Document]:
    stmt = select(Document)
    if q:
        stmt = stmt.where(or_(Document.title.ilike(f"%{q}%"), Document.doc_type.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Document.status == status)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    docs = db.execute(stmt.order_by(Document.updated_at.desc())).scalars().all()
    return [d for d in docs if can_view(user, d)]
