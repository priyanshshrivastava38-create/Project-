# MetalFlow ERP

Manufacturing ERP for metal fabrication shops: sales orders → material reservation → production
stages → quality inspection → delivery, with an inventory ledger, documents, reports, an audit log
and a document-grounded assistant.

**Stack:** FastAPI · SQLAlchemy · Alembic · PostgreSQL · React 18 · Vite · Docker

[![CI](https://github.com/priyanshshrivastava38-create/Project-/actions/workflows/ci.yml/badge.svg)](https://github.com/priyanshshrivastava38-create/Project-/actions/workflows/ci.yml)

---

## Deploy (one click, free)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/priyanshshrivastava38-create/Project-)

1. Click the button and sign in to Render (GitHub login works).
2. Fill in two fields:
   - `ADMIN_EMAIL`: the email you will sign in with
   - `ADMIN_PASSWORD`: at least 12 characters
3. Click **Apply**. Render creates the database and the app and connects them (first build ≈5–8 min).
4. Open the `https://metalflow-erp-….onrender.com` link, sign in, and add your team under **Admin → Users**.
5. Remove `ADMIN_PASSWORD` from the service's **Environment** tab (it is only used for the first login).

> **Free plan limits:** the app sleeps after 15 minutes idle (the next visit takes ≈1 minute), and
> Render's **free database is deleted 30 days after creation**. Upgrade the database in Render
> (`metalflow-db` → Upgrade) before then, or move to another Postgres. See
> [docs/deployment.md](docs/deployment.md).

**If a deploy fails**, open the service's **Logs**: configuration and database problems are shown in
a `STARTUP CHECK FAILED` box with the fix. Render allows one free database per account, so delete an
old one first if the Blueprint cannot create `metalflow-db`.

### Other ways to deploy

- **Any server with Docker:** every green build on `main` publishes an image:
  ```bash
  docker run -p 8000:8000 \
    -e DATABASE_URL=postgresql://user:password@host:5432/metalflow \
    -e ENVIRONMENT=production -e REFRESH_COOKIE_SECURE=true \
    -e JWT_SECRET_KEY="$(openssl rand -base64 48)" \
    -e ADMIN_EMAIL=you@example.com -e ADMIN_PASSWORD='a-long-password' \
    ghcr.io/priyanshshrivastava38-create/metalflow-erp:latest
  ```
  Put HTTPS (Caddy, nginx, a load balancer) in front of it.
- **Docker Compose on one machine** (database + API + nginx frontend): see below.

---

## Run locally

### With Docker Compose

```bash
cp .env.example .env        # then set POSTGRES_PASSWORD and JWT_SECRET_KEY
docker compose up --build
```

App: http://localhost:8080 · API docs: http://localhost:8000/api/docs ·
Demo login: `admin@metalflow.example` / the `DEMO_PASSWORD` from `.env`.

### Without Docker (for development)

Requires Python 3.12, Node 20 and a local PostgreSQL.

```bash
# Backend: http://localhost:8000
createdb metalflow
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed          # demo data; password MetalFlow-demo-2026
.venv/bin/uvicorn app.main:app --reload

# Frontend: http://localhost:5173 (proxies /api to the backend)
cd frontend
npm ci && npm run dev
```

Sign in as `admin@metalflow.example` / `MetalFlow-demo-2026` (other demo roles: `sales@`,
`inventory@`, `production@`, `quality@`, `dispatch@`, `management@metalflow.example`).

---

## Tests

```bash
cd backend && createdb metalflow_test && .venv/bin/pytest     # needs PostgreSQL
cd frontend && npm test && npm run lint
```

CI runs lint, migrations (up/down/up), backend and frontend tests and the Docker builds on every push.

## Configuration

All settings come from environment variables; [.env.example](.env.example) lists them with comments.
The important ones in production:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgres://`, `postgresql://` accepted) |
| `JWT_SECRET_KEY` | ≥32 random characters; the app refuses to start without it in production |
| `ENVIRONMENT` | `production` enables HSTS, disables API docs, enforces the checks above |
| `REFRESH_COOKIE_SECURE` | `true` behind HTTPS |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | create the first admin on an empty database |
| `AI_PROVIDER` / `AI_API_KEY` | optional LLM for the assistant (`none`, `openai`, `anthropic`) |

## Documentation

[Architecture](docs/architecture.md) · [Business workflows](docs/business-workflows.md) ·
[Database schema](docs/database-schema.md) · [API guide](docs/api-guide.md) ·
[Security](docs/security.md) · [Deployment](docs/deployment.md) · [Testing](docs/testing.md) ·
[Demo script](docs/demo-script.md)

```
backend/    FastAPI app (app/), Alembic migrations, scripts (seed, bootstrap, preflight), tests
frontend/   React SPA (src/pages, src/components, src/api), nginx config for the compose image
docs/       design, API and operations documentation
Dockerfile  single production image: built SPA served by the API (used by Render)
render.yaml Render Blueprint: database + web service
```
