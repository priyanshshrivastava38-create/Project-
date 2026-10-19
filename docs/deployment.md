# Deployment

## Option A: Render (Blueprint, one click)

`render.yaml` provisions a PostgreSQL database and one Docker web service built from the root
`Dockerfile` (React build + FastAPI), wired together automatically. On start the container runs
`python -m scripts.preflight` (validates settings, waits for the database, prints a plain-English fix
on failure), `alembic upgrade head`, then either seeds demo data (`SEED_DEMO_DATA=true`, empty DB
only) or runs `python -m scripts.bootstrap`, which creates production stages, default warehouses and,
on an empty `users` table, the first admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Then uvicorn starts.

1. Render dashboard → **New → Blueprint** → select the repo.
2. Enter `ADMIN_EMAIL` and `ADMIN_PASSWORD` (≥12 chars) → **Apply**.
3. Wait for the first deploy (≈5–8 min; health check `/health/ready`).
4. Open the service URL, sign in as that admin and create the other users under *Admin → Users*.
   Then delete `ADMIN_PASSWORD` from the service's environment (only read while no users exist).

If the deploy fails, the log shows a `STARTUP CHECK FAILED` box with the reason and the fix.

**Free-tier caveats:** the web service sleeps after 15 min idle (first request ≈1 min), and Render's
**free PostgreSQL is deleted 30 days after creation**. Before then, upgrade it (dashboard →
`metalflow-db` → Upgrade) or move to another Postgres such as Neon: remove the `databases` block from
`render.yaml` and change `DATABASE_URL` to `sync: false`, then paste the connection string (a pasted
`psql '...'` command or missing `?sslmode=require` for Neon is corrected automatically).

For a throwaway demo instead: set `SEED_DEMO_DATA=true` and a `DEMO_PASSWORD` before the first deploy.
Demo accounts: `admin@`, `sales@`, `inventory@`, `production@`, `quality@`, `dispatch@`,
`management@metalflow.example`.

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
