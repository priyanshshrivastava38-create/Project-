"""Login, refresh-token rotation and logout.

Access tokens: short-lived JWTs sent as ``Authorization: Bearer``; the SPA keeps them in memory only.
Refresh tokens: opaque random strings in an httpOnly, SameSite=strict cookie scoped to /api/v1/auth,
stored as SHA-256 hashes. Each refresh rotates the token; presenting an already-rotated token
revokes the whole token family (theft detection).
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, hash_token, new_refresh_token, verify_password
from app.models import RefreshToken, User
from app.schemas.auth import UserCreate, UserUpdate
from app.services import audit
from app.services.common import get_or_404

logger = logging.getLogger("metalflow.auth")
# Verified against when the e-mail is unknown, so response time does not reveal which accounts exist.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _issue_refresh(db: Session, user: User, family_id: str | None = None) -> str:
    raw, hashed = new_refresh_token()
    now = datetime.now(UTC)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hashed,
            family_id=family_id or secrets.token_hex(16),
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
            created_at=now,
        )
    )
    return raw


def login(db: Session, email: str, password: str) -> tuple[str, int, str, User]:
    user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise AuthenticationError("Invalid email or password")
    if not verify_password(password, user.hashed_password):
        logger.info("Failed login for user_id=%s", user.id)
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    user.last_login_at = datetime.now(UTC)
    access, expires = create_access_token(user.id, user.role)
    refresh = _issue_refresh(db, user)
    audit.record(db, user, "auth.login", "user", user.id, f"{user.email} logged in")
    db.commit()
    return access, expires, refresh, user


def refresh(db: Session, raw_token: str | None) -> tuple[str, int, str]:
    if not raw_token:
        raise AuthenticationError("Missing refresh token")
    token = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if token is None:
        raise AuthenticationError("Invalid refresh token")
    if token.revoked_at is not None:
        # Reuse of a rotated token: revoke every token in the family.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        logger.warning("Refresh token reuse detected for user_id=%s; family revoked", token.user_id)
        raise AuthenticationError("Refresh token reuse detected; please sign in again")
    if token.expires_at < now:
        raise AuthenticationError("Refresh token expired")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User inactive or not found")
    token.revoked_at = now
    new_raw = _issue_refresh(db, user, token.family_id)
    access, expires = create_access_token(user.id, user.role)
    db.commit()
    return access, expires, new_raw


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    token = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))).scalar_one_or_none()
    if token:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()


def revoke_user_tokens(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def create_user(db: Session, actor: User, data: UserCreate) -> User:
    email = data.email.lower()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise ConflictError(f"A user with email {email} already exists")
    u = User(email=email, full_name=data.full_name, role=data.role, hashed_password=hash_password(data.password), is_active=True)
    db.add(u)
    db.flush()
    audit.record(db, actor, "user.create", "user", u.id, f"Created user {email} with role {data.role}")
    db.commit()
    return u


def update_user(db: Session, actor: User, user_id: int, data: UserUpdate) -> User:
    u = get_or_404(db, User, user_id, "User", lock=True)
    changes = data.model_dump(exclude_unset=True)
    if u.id == actor.id and (changes.get("role") not in (None, u.role) or changes.get("is_active") is False):
        raise ConflictError("You cannot change your own role or deactivate your own account")
    if "password" in changes:
        u.hashed_password = hash_password(changes.pop("password"))
        revoke_user_tokens(db, u.id)
    if changes.get("is_active") is False or changes.get("role") not in (None, u.role):
        revoke_user_tokens(db, u.id)
    for k, v in changes.items():
        setattr(u, k, v)
    audit.record(
        db, actor, "user.update", "user", u.id, f"Updated user {u.email}", {"fields": sorted(data.model_dump(exclude_unset=True))}
    )
    db.commit()
    return u
