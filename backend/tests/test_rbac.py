"""Authorization: endpoints reject unauthenticated callers and roles without the permission."""

import pytest

from app.permissions.policy import Role

PROTECTED = [
    ("get", "/orders"),
    ("get", "/inventory"),
    ("get", "/production/jobs"),
    ("get", "/quality/inspections"),
    ("get", "/deliveries"),
    ("get", "/documents"),
    ("get", "/dashboard/summary"),
    ("post", "/assistant/chat"),
    ("get", "/audit-logs"),
    ("get", "/users"),
    ("post", "/inventory/adjustments"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_requires_authentication(client, method, path):
    r = getattr(client, method)("/api/v1" + path)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_sales_cannot_adjust_inventory(as_role, ids):
    r = as_role(Role.SALES).post(
        "/inventory/adjustments",
        {
            "item_type": "MATERIAL",
            "item_id": ids["sheet"],
            "warehouse_id": ids["rm"],
            "quantity_delta": "10",
            "reason": "trying it",
        },
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


def test_sales_cannot_receive_inventory(as_role, ids):
    r = as_role(Role.SALES).post("/inventory/receipts", {"material_id": ids["sheet"], "warehouse_id": ids["rm"], "quantity": "5"})
    assert r.status_code == 403


def test_management_is_read_only(as_role, ids):
    m = as_role(Role.MANAGEMENT)
    assert m.get("/dashboard/summary").status_code == 200
    assert m.get("/orders").status_code == 200
    assert (
        m.post("/orders", {"customer_id": ids["customer"], "items": [{"product_id": ids["brk"], "quantity": "1"}]}).status_code
        == 403
    )
    assert m.post("/customers", {"company_name": "Nope Ltd"}).status_code == 403


def test_dispatch_cannot_create_production_jobs(as_role, flow):
    o = flow.order("10")
    assert as_role(Role.DISPATCH).post("/production/jobs", {"order_item_id": o["items"][0]["id"]}).status_code == 403


def test_quality_inspector_cannot_edit_orders_or_users(as_role, flow):
    o = flow.order("10", confirm=False)
    qa = as_role(Role.QUALITY_INSPECTOR)
    assert qa.patch(f"/orders/{o['id']}", {"notes": "x"}).status_code == 403
    assert (
        qa.post(
            "/users", {"email": "qa2@test.example", "full_name": "QA Two", "role": "ADMIN", "password": "long-enough-pw"}
        ).status_code
        == 403
    )


def test_only_admin_reads_audit_log(as_role):
    assert as_role(Role.ADMIN).get("/audit-logs").status_code == 200
    assert as_role(Role.MANAGEMENT).get("/audit-logs").status_code == 403
