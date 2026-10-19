"""Startup check: explain configuration and database problems in plain words before migrations run.

Usage:  python -m scripts.preflight      (run by start.sh; exits non-zero with a hint on failure)

Waits up to PREFLIGHT_DB_WAIT_SECONDS (default 90) for the database, because a freshly created
managed database can take a minute to accept connections on the first deploy.
"""

import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

HINTS = [
    ("password authentication failed", "The database password in DATABASE_URL is wrong. Copy the connection string again."),
    ("could not translate host name", "The database host name in DATABASE_URL is wrong or cut off. Copy the full string again."),
    ("name or service not known", "The database host name in DATABASE_URL is wrong or cut off. Copy the full string again."),
    ("does not exist", "The database name at the end of DATABASE_URL does not exist on that server."),
    ("ssl", "The server requires TLS: add ?sslmode=require to the end of DATABASE_URL."),
    ("endpoint", "Use the full Neon connection string (it includes the endpoint host and ?sslmode=require)."),
    ("timeout", "The database did not answer. Check it is running and reachable from this service."),
    ("connection refused", "Nothing accepts connections at that host/port. Check the database is running."),
]


def fail(message: str) -> None:
    print("\n" + "=" * 70, file=sys.stderr)
    print("STARTUP CHECK FAILED", file=sys.stderr)
    print(message, file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    try:
        from app.core.config import get_settings

        settings = get_settings()
    except Exception as exc:  # invalid env values: show which one, not a traceback
        fail(f"Invalid configuration: {exc}")

    url = settings.database_url
    try:
        parsed = make_url(url)
    except Exception:
        fail("DATABASE_URL is not a valid connection string. It must start with postgresql://")
    if settings.is_production and parsed.host in (None, "localhost", "127.0.0.1"):
        fail("DATABASE_URL is not set. On Render it comes from the database in render.yaml; elsewhere set it.")

    target = f"{parsed.host}:{parsed.port or 5432}/{parsed.database}"
    wait = int(os.environ.get("PREFLIGHT_DB_WAIT_SECONDS", "90"))
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    deadline = time.monotonic() + wait
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Database reachable at {target}.")
            return
        except Exception as exc:
            reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0] if str(exc) else type(exc).__name__
            low = reason.lower()
            hint = next((h for needle, h in HINTS if needle in low), None)
            # Retrying cannot fix bad credentials or a wrong database name.
            permanent = "password authentication failed" in low or "does not exist" in low
            if permanent or time.monotonic() >= deadline:
                fail(f"Cannot connect to the database at {target}.\nReason: {reason}\nFix:    {hint or 'Check DATABASE_URL.'}")
            print(f"Waiting for database at {target} (attempt {attempt}): {reason}")
            time.sleep(5)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
