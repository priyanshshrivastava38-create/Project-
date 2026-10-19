from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    details: dict | None = None,
) -> None:
    """Add an audit entry to the current transaction (committed with the business change)."""
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary[:300],
            details=details or {},
        )
    )
