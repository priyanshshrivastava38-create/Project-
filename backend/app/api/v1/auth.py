from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser, require
from app.core.errors import AuthenticationError
from app.core.ratelimit import login_limiter
from app.models import User
from app.permissions.policy import P, permissions_for
from app.schemas.auth import LoginRequest, MeOut, TokenResponse, UserCreate, UserOut, UserUpdate
from app.schemas.common import Message, Page, PageParams
from app.services import auth as svc
from app.services.common import get_or_404, paginate

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
COOKIE = "mf_refresh"
COOKIE_PATH = "/api/v1/auth"


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=s.refresh_cookie_secure,
        samesite=s.refresh_cookie_samesite,
        max_age=s.refresh_token_expire_days * 86400,
        path=COOKIE_PATH,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid credentials"}, 429: {"description": "Too many failed attempts"}},
)
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> TokenResponse:
    """Exchange email/password for a short-lived access token. A rotating refresh token is set as an httpOnly cookie.

    Repeated failures for the same account from the same IP (or many failures from one IP) return 429."""
    s = get_settings()
    ip = request.client.host if request.client else "unknown"
    account_key, ip_key = f"acct:{body.email.lower()}|{ip}", f"ip:{ip}"
    login_limiter.check(
        [(account_key, s.login_max_failures_per_account), (ip_key, s.login_max_failures_per_ip)], s.login_rate_window_seconds
    )
    try:
        access, expires, refresh, _ = svc.login(db, body.email, body.password)
    except AuthenticationError:
        login_limiter.fail([account_key, ip_key])
        raise
    login_limiter.clear(account_key)
    _set_cookie(response, refresh)
    return TokenResponse(access_token=access, expires_in=expires)


@router.post("/refresh", response_model=TokenResponse, responses={401: {"description": "Missing, expired or reused token"}})
def refresh(response: Response, db: DB, mf_refresh: str | None = Cookie(default=None)) -> TokenResponse:
    access, expires, new_refresh = svc.refresh(db, mf_refresh)
    _set_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in=expires)


@router.post("/logout", response_model=Message)
def logout(response: Response, db: DB, mf_refresh: str | None = Cookie(default=None)) -> Message:
    svc.logout(db, mf_refresh)
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return Message(message="Logged out")


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> dict:
    return {**UserOut.model_validate(user).model_dump(), "permissions": permissions_for(user.role)}


@users_router.get("", response_model=Page[UserOut])
def list_users(
    db: DB, pp: PageParams = Depends(), q: str | None = None, role: str | None = None, _: User = Depends(require(P.USERS_MANAGE))
) -> dict:
    stmt = select(User)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%") | User.full_name.ilike(f"%{q}%"))
    if role:
        stmt = stmt.where(User.role == role)
    items, total = paginate(db, stmt.order_by(User.full_name), pp.page, pp.page_size)
    return {"items": items, "total": total, "page": pp.page, "page_size": pp.page_size}


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, actor: User = Depends(require(P.USERS_MANAGE))) -> User:
    return svc.create_user(db, actor, body)


@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DB, _: User = Depends(require(P.USERS_MANAGE))) -> User:
    return get_or_404(db, User, user_id, "User")


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DB, actor: User = Depends(require(P.USERS_MANAGE))) -> User:
    return svc.update_user(db, actor, user_id, body)
