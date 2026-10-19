# Single-service production image (used by Render): builds the React SPA and serves it from the
# FastAPI app, so the browser talks to one origin (httpOnly refresh cookie, no CORS).
# Static build output is architecture-independent: build it natively even for multi-arch images.
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FRONTEND_DIST_DIR=/app/frontend_dist
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini backend/start.sh ./
COPY backend/scripts ./scripts
COPY --from=frontend /web/dist ./frontend_dist
RUN useradd --create-home --uid 10001 metalflow && chown -R metalflow /app
USER metalflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\").status==200 else 1)"
CMD ["./start.sh"]
