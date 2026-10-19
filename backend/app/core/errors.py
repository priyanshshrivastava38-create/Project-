"""Domain exceptions and structured error responses.

Every error returned by the API has the shape::

    {"error": {"code": "...", "message": "...", "details": ...}}
"""

import logging
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("metalflow.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Duplicate data or an operation that conflicts with current state."""

    status_code = 409
    code = "conflict"


class BusinessRuleError(AppError):
    """A request that is well-formed but violates a business rule."""

    status_code = 422
    code = "business_rule_violation"


class InvalidTransitionError(BusinessRuleError):
    code = "invalid_state_transition"


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


def _body(code: str, message: str, details: object | None = None) -> dict:
    details = jsonable_encoder(details, custom_encoder={Decimal: lambda d: format(d, "f")})
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        headers = None
        if isinstance(exc, AuthenticationError):
            headers = {"WWW-Authenticate": "Bearer"}
        elif isinstance(exc, RateLimitedError) and isinstance(exc.details, dict):
            headers = {"Retry-After": str(exc.details.get("retry_after_seconds", 60))}
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body("validation_error", "Request validation failed", details))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body("http_error", str(exc.detail)))

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        # Constraint violations that slipped past service validation (e.g. concurrent duplicates).
        logger.warning("Integrity error: %s", type(exc.orig).__name__ if exc.orig else "unknown")
        return JSONResponse(
            status_code=409, content=_body("conflict", "The request conflicts with existing data or a concurrent change")
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content=_body("internal_error", "An unexpected error occurred"))
