from app.permissions.policy import Role


def test_dashboard_reflects_database_changes(as_role, flow):
    admin = as_role(Role.ADMIN)
    before = admin.get("/dashboard/summary").json()
    o = flow.order("10")
    mid = admin.get("/dashboard/summary").json()
    assert mid["total_orders"] == before["total_orders"] + 1
    assert mid["orders_awaiting_production"] == before["orders_awaiting_production"] + 1
    flow.job(o)
    after = admin.get("/dashboard/summary").json()
    assert after["active_production_jobs"] == before["active_production_jobs"] + 1
    assert after["orders_awaiting_production"] == before["orders_awaiting_production"]
    assert any(a["action"] == "production.start" for a in after["recent_activity"])


def test_dashboard_trend_and_reports(as_role, flow):
    flow.completed_order("10")
    m = as_role(Role.MANAGEMENT)
    trend = m.get("/dashboard/production", params={"days": 7}).json()
    assert len(trend["series"]) == 8 and trend["series"][-1]["jobs_completed"] >= 1
    assert m.get("/reports/production-performance").json()["completed_jobs"] >= 1
    assert m.get("/reports/quality").json()["inspections"] >= 1
    assert m.get("/reports/orders-by-customer").status_code == 200
    assert m.get("/reports/fulfillment").status_code == 200


def test_audit_log_records_actions_with_user(as_role, flow):
    o = flow.order("3")
    logs = as_role(Role.ADMIN).get("/audit-logs", params={"entity_type": "order", "entity_id": o["id"]}).json()["items"]
    actions = {entry["action"] for entry in logs}
    assert {"order.create", "order.confirmed"} <= actions
    assert all(entry["user"]["full_name"] == "Sales User" for entry in logs)


def test_health_endpoints(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").json()["database"] == "ok"
