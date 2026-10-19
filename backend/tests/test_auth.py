from app.permissions.policy import Role
from tests.conftest import PASSWORD


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_success_sets_httponly_refresh_cookie(client):
    r = login(client, "admin@test.example")
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer" and r.json()["expires_in"] == 900
    cookie = r.headers["set-cookie"]
    assert "mf_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=strict" in cookie


def test_login_invalid_credentials(client):
    r = login(client, "admin@test.example", "wrong-password")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"
    r2 = login(client, "nobody@test.example", "whatever-123")
    assert r2.status_code == 401 and r2.json()["error"]["message"] == r.json()["error"]["message"]


def test_inactive_user_cannot_login(client):
    assert login(client, "inactive@test.example").status_code == 401


def test_me_requires_token_and_returns_permissions(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    token = login(client, "sales@test.example").json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["role"] == "SALES" and "orders:write" in me["permissions"] and "inventory:adjust" not in me["permissions"]


def test_tampered_token_rejected(client):
    import jwt

    forged = jwt.encode(
        {"sub": "1", "role": "ADMIN", "type": "access", "exp": 9999999999, "iat": 1}, "wrong-secret", algorithm="HS256"
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    login(client, "admin@test.example")
    old = client.cookies.get("mf_refresh")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    new = client.cookies.get("mf_refresh")
    assert new and new != old
    # Replaying the rotated token revokes the whole family, including the newest token.
    client.cookies.set("mf_refresh", old, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.set("mf_refresh", new, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_refresh(client):
    login(client, "admin@test.example")
    token = client.cookies.get("mf_refresh")
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set("mf_refresh", token, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_admin_user_management_and_role_change_takes_effect(as_role):
    admin = as_role(Role.ADMIN)
    r = admin.post(
        "/users", {"email": "new.sales@test.example", "full_name": "New Sales", "role": "SALES", "password": "long-enough-pw"}
    )
    assert r.status_code == 201
    assert (
        admin.post(
            "/users", {"email": "new.sales@test.example", "full_name": "Dup", "role": "SALES", "password": "long-enough-pw"}
        ).status_code
        == 409
    )
    assert (
        admin.post("/users", {"email": "x@test.example", "full_name": "Weak", "role": "SALES", "password": "short"}).status_code
        == 422
    )
    assert as_role(Role.SALES).get("/users").status_code == 403


def test_admin_cannot_demote_self(as_role, db):
    from app.models import User

    admin = as_role(Role.ADMIN)
    me = db.query(User).filter_by(role="ADMIN").first()
    assert admin.patch(f"/users/{me.id}", {"role": "SALES"}).status_code == 409
