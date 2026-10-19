# Deployment

## Option A: Render + Neon (Blueprint, free tier)

`render.yaml` provisions one Docker web service built from the root `Dockerfile` (React build +
FastAPI) and expects an external PostgreSQL database such as Neon (free, does not expire). On start
the container runs `alembic upgrade head`, then either seeds demo data (`SEED_DEMO_DATA=true`, empty
DB only) or runs `python -m scripts.bootstrap`, which creates missing production stages, default
warehouses and, on an empty `users` table, the first admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`
(start fails with a clear message if they are missing). Then uvicorn starts on `$PORT`.

1. Neon (neon.tech) → create a project → copy the connection string
   (`postgresql://user:password@host/dbname?sslmode=require`).
2. Render dashboard → **New → Blueprint** → select the repo → Render reads `render.yaml`.
3. Fill in the prompted values: `DATABASE_URL` (the Neon string), `ADMIN_EMAIL`,
   `ADMIN_PASSWORD` (≥12 chars) → **Apply**.
4. Wait for the first deploy (≈5–8 min). The health check is `/health/ready`.
5. Open the service URL, sign in as that admin and create the other users under *Admin → Users*.
   Then delete `ADMIN_PASSWORD` from the service's environment (it is only read while no users exist).
6. For a throwaway demo instead: set `SEED_DEMO_DATA=true` and a `DEMO_PASSWORD` before the first deploy.
   Demo accounts: `admin@`, `sales@`, `inventory@`, `production@`, `quality@`, `dispatch@`,
   `management@metalflow.example`.

Free-tier caveats: the Render web service sleeps after 15 min idle (first request ≈1 min), and
Neon's free tier has limited storage and short backup history. Use paid plans for real business data.

Optional LLM: set `AI_PROVIDER` (`openai` or `anthropic`), `AI_API_KEY`, optionally `AI_MODEL`/`AI_BASE_URL`.

## Option B: Docker Compose (local or a single VM)

```bash
cp .env.example .env      # set POSTGRES_PASSWORD, JWT_SECRET_KEY, DEMO_PASSWORD
docker compose up --build
# frontend http://localhost:8080 · API docs http://localhost:8000/api/docs
```

For a VM: put TLS in front (Caddy/nginx), set `ENVIRONMENT=production`, `REFRESH_COOKIE_SECURE=true`,
`CORS_ORIGINS=https://your-domain`, and back up the `pgdata` volume (`pg_dump -Fc`) on a schedule.

## Production checklist
* Strong `JWT_SECRET_KEY` (≥32 chars; the app refuses weak secrets in production).
* `REFRESH_COOKIE_SECURE=true` behind HTTPS.
* Demo seeding off (`SEED_DEMO_DATA=false`, the Render default); first admin via `ADMIN_EMAIL`/`ADMIN_PASSWORD`.
* Paid plans for real data (Render free web services sleep; use a Postgres plan with backups and point-in-time restore).
* Database backups and a restore drill; run migrations after a backup.
* Login throttling is built in but per process; add proxy/Redis limiting if you run several workers.
* Log shipping (access lines carry `rid=<X-Request-ID>`), uptime monitoring on `/health/ready`.
