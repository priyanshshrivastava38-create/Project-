"""Production hardening: login throttling, response headers, bootstrap script."""

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import StageDefinition, User, Warehouse
from tests.conftest import PASSWORD


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_repeated_failed_logins_are_throttled(client):
    limit = get_settings().login_max_failures_per_account
    for _ in range(limit):
        assert login(client, "sales@test.example", "wrong-password").status_code == 401
    r = login(client, "sales@test.example")  # correct password, but the account+IP is locked out
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) > 0
    # Other accounts from the same IP are unaffected below the per-IP limit.
    assert login(client, "admin@test.example").status_code == 200


def test_successful_login_clears_failure_count(client):
    limit = get_settings().login_max_failures_per_account
    for _ in range(limit - 1):
        login(client, "sales@test.example", "wrong-password")
    assert login(client, "sales@test.example").status_code == 200
    for _ in range(limit - 1):
        assert login(client, "sales@test.example", "wrong-password").status_code == 401


def test_security_headers_and_request_id(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert client.get("/health").headers["X-Request-ID"]  # generated when absent


@pytest.fixture()
def bootstrap_db(db, monkeypatch):
    """Run the bootstrap script inside the test transaction."""
    from scripts import bootstrap

    monkeypatch.setattr(bootstrap, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    return bootstrap


def test_bootstrap_requires_admin_credentials_on_empty_db(bootstrap_db, monkeypatch):
    monkeypatch.setattr(bootstrap_db, "_has_users", lambda db: False)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(SystemExit):
        bootstrap_db.main()


def test_bootstrap_creates_admin_and_reference_data_idempotently(bootstrap_db, db, monkeypatch):
    users_before = {u.id for u in db.execute(select(User)).scalars()}
    calls = iter([False, True])
    monkeypatch.setattr(bootstrap_db, "_has_users", lambda db: next(calls))
    monkeypatch.setenv("ADMIN_EMAIL", "Owner@Plant.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-very-long-password")
    bootstrap_db.main()
    bootstrap_db.main()
    created = [u for u in db.execute(select(User)).scalars() if u.id not in users_before]
    assert [(u.email, u.role) for u in created] == [("owner@plant.example", "ADMIN")]
    codes = set(db.execute(select(StageDefinition.code)).scalars())
    assert {"MACHINING", "ASSEMBLY", "CUTTING"} <= codes
    assert db.execute(select(Warehouse.id)).first()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        ("https://a.example, https://b.example", ["https://a.example", "https://b.example"]),
        ('["https://a.example"]', ["https://a.example"]),
    ],
)
def test_cors_origins_env_formats(monkeypatch, raw, expected):
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == expected


def test_blank_enable_api_docs_means_default(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("ENABLE_API_DOCS", "")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings(_env_file=None).api_docs_enabled is False
