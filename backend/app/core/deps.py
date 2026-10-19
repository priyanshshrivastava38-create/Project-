"""FastAPI dependencies: DB session, current user, permission checks."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models import User
from app.permissions.policy import P, has_permission

bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AuthenticationError("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User inactive or not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(permission: P) -> Callable[..., User]:
    """Dependency factory: ``user: User = Depends(require(P.ORDERS_WRITE))``."""

    def checker(user: CurrentUser) -> User:
        if not has_permission(user.role, permission):
            raise PermissionDeniedError(f"Your role does not allow '{permission.value}'")
        return user

    return checker
