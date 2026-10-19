from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus
from app.permissions.policy import Role
from app.schemas.common import ORM, UserRef


class VersionOut(ORM):
    id: int
    version_number: int
    status: DocumentStatus
    source_filename: str
    content_type: str
    size_bytes: int
    content_hash: str
    page_count: int | None
    extraction_note: str | None
    uploaded_by: UserRef | None
    uploaded_at: datetime
    approved_by: UserRef | None
    approved_at: datetime | None


class DocumentOut(ORM):
    id: int
    title: str
    doc_type: str
    status: DocumentStatus
    allowed_roles: list[Role]
    created_at: datetime
    updated_at: datetime
    versions: list[VersionOut]


class ApprovalIn(BaseModel):
    version_id: int | None = Field(default=None, description="Defaults to the latest draft version")
    comment: str | None = Field(default=None, max_length=500)


class ApprovalOut(ORM):
    id: int
    version_id: int
    action: str
    comment: str | None
    user: UserRef | None
    created_at: datetime
