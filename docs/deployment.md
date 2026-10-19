# Deployment

## Option A: Render (Blueprint, used for the demo deployment)

`render.yaml` provisions a PostgreSQL database and one Docker web service built from the root
`Dockerfile` (React build + FastAPI). On start the container runs `alembic upgrade head`, then either
seeds demo data (`SEED_DEMO_DATA=true`, empty DB only) or runs `python -m scripts.bootstrap`, which
creates missing production stages, default warehouses and, on an empty `users` table, the first admin
from `ADMIN_EMAIL`/`ADMIN_PASSWORD` (start fails with a clear message if they are missing). Then uvicorn
starts on `$PORT`.

1. Push the repository to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo → **Apply**.
3. Wait for the first deploy (≈5–8 min). The health check is `/health/ready`.
4. Render prompts for `ADMIN_EMAIL` and `ADMIN_PASSWORD` (≥12 chars). Open the service URL, sign in as
   that admin and create the other users under *Admin → Users*. Then delete `ADMIN_PASSWORD` from the
   service's environment (it is only read while no users exist).
5. For a throwaway demo instead: set `SEED_DEMO_DATA=true` and a `DEMO_PASSWORD` before the first deploy.
   Demo accounts: `admin@`, `sales@`, `inventory@`, `production@`, `quality@`, `dispatch@`,
   `management@metalflow.example`.

Free-tier caveats: the web service sleeps after 15 min idle (first request ≈1 min), and Render's
free PostgreSQL expires after 30 days. Use paid plans for anything beyond a demo.

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
* Paid Render plans (free web services sleep; free PostgreSQL expires after 30 days and has no backups).
* Database backups and a restore drill; run migrations after a backup.
* Login throttling is built in but per process; add proxy/Redis limiting if you run several workers.
* Log shipping (access lines carry `rid=<X-Request-ID>`), uptime monitoring on `/health/ready`.
