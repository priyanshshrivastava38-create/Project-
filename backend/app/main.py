import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
access_log = logging.getLogger("metalflow.access")
settings = get_settings()
if settings.is_production and not settings.refresh_cookie_secure:
    logging.getLogger("metalflow").warning("REFRESH_COOKIE_SECURE is false in production; set it to true behind HTTPS")

# The SPA loads Inter from Google Fonts; recharts and a few components set inline styles.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)

app = FastAPI(
    title="MetalFlow ERP API",
    version="1.0.0",
    description="Manufacturing ERP workflow API. Authenticate via `POST /api/v1/auth/login`, then send "
    '`Authorization: Bearer <access_token>`. All errors use `{"error": {code, message, details}}`.',
    docs_url="/api/docs" if settings.api_docs_enabled else None,
    redoc_url="/api/redoc" if settings.api_docs_enabled else None,
    openapi_url="/api/openapi.json" if settings.api_docs_enabled else None,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
register_exception_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Request id (echoed as X-Request-ID), access log line with timing, and security headers."""
    request_id = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if not request.url.path.startswith("/health"):
        access_log.info("%s %s %s %.1fms rid=%s", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
    h = response.headers
    h["X-Request-ID"] = request_id
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(("/api/docs", "/api/redoc")):  # Swagger UI loads assets from a CDN
        h.setdefault("Content-Security-Policy", CSP)
    if settings.is_production:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "database": "ok"})
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)


# Single-service deployment: serve the built React app from the API container.
if settings.frontend_dist_dir and os.path.isdir(settings.frontend_dist_dir):
    dist = os.path.realpath(settings.frontend_dist_dir)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found", "details": None}}, status_code=404)
        candidate = os.path.realpath(os.path.join(dist, path))
        if path and candidate.startswith(dist + os.sep) and os.path.isfile(candidate):
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in candidate else None
            return FileResponse(candidate, headers=headers)
        return FileResponse(os.path.join(dist, "index.html"), headers={"Cache-Control": "no-cache"})
