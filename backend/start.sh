#!/bin/sh
# Container entrypoint: apply migrations, seed demo data or bootstrap reference data, then serve.
set -e
echo "Applying database migrations..."
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m scripts.seed
else
  python -m scripts.bootstrap
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" --workers "${WEB_CONCURRENCY:-1}" \
  --timeout-graceful-shutdown 20 --no-server-header
