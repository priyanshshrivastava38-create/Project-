from decimal import Decimal as D

from app.permissions.policy import Role


def test_customer_crud_validation_and_duplicates(as_role):
    s = as_role(Role.SALES)
    r = s.post("/customers", {"company_name": "Forge & Co", "email": "ops@forge.example", "phone": "+44 1234 567890"})
    assert r.status_code == 201 and r.json()["code"].startswith("CUST-")
    cid = r.json()["id"]
    assert s.post("/customers", {"company_name": "forge & co"}).status_code == 409
    assert s.post("/customers", {"company_name": "Other", "email": "not-an-email"}).status_code == 422
    assert s.patch(f"/customers/{cid}", {"contact_person": "Ann"}).json()["contact_person"] == "Ann"
    page = s.get("/customers", params={"q": "forge", "page_size": 5}).json()
    assert page["total"] == 1 and page["items"][0]["id"] == cid
    assert s.get("/customers", params={"sort": "drop table"}).status_code == 422


def test_cannot_deactivate_customer_with_open_orders(as_role, flow, ids):
    flow.order("5", confirm=False)
    r = as_role(Role.SALES).patch(f"/customers/{ids['customer']}", {"status": "INACTIVE"})
    assert r.status_code == 422


def test_order_totals_calculated_server_side(as_role, ids):
    r = as_role(Role.SALES).post(
        "/orders",
        {
            "customer_id": ids["customer"],
            "tax_rate": "20",
            "total": "1.00",
            "subtotal": "0.01",
            "items": [{"product_id": ids["brk"], "quantity": "500", "unit_price": "4.20", "line_total": "1"}],
        },
    )
    assert r.status_code == 201
    o = r.json()
    assert o["order_number"].startswith("SO-") and o["status"] == "DRAFT"
    assert (D(o["subtotal"]), D(o["tax_amount"]), D(o["total"])) == (D("2100.00"), D("420.00"), D("2520.00"))
    assert D(o["items"][0]["line_total"]) == D("2100.00")


def test_order_validation(as_role, ids):
    s = as_role(Role.SALES)
    base = {"customer_id": ids["customer"], "items": [{"product_id": ids["brk"], "quantity": "1"}]}
    assert s.post("/orders", {**base, "items": []}).status_code == 422
    assert s.post("/orders", {**base, "items": [{"product_id": ids["brk"], "quantity": "-5"}]}).status_code == 422
    assert (
        s.post("/orders", {**base, "items": [{"product_id": ids["brk"], "quantity": "1", "unit_price": "-1"}]}).status_code == 422
    )
    assert s.post("/orders", {**base, "order_date": "2026-10-10", "required_date": "2026-10-01"}).status_code == 422
    assert s.post("/orders", {**base, "customer_id": ids["inactive_customer"]}).status_code == 422
    assert s.post("/orders", {**base, "customer_id": 999999}).status_code == 404


def test_confirm_and_invalid_transitions(as_role, flow):
    s = as_role(Role.SALES)
    o = flow.order("10", confirm=False)
    r = s.post(f"/orders/{o['id']}/confirm")
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"
    again = s.post(f"/orders/{o['id']}/confirm")
    assert again.status_code == 422 and again.json()["error"]["code"] == "invalid_state_transition"
    assert [h["to_status"] for h in r.json()["history"]] == ["DRAFT", "CONFIRMED"]


def test_no_edits_after_confirmation_except_notes(as_role, flow, ids):
    s = as_role(Role.SALES)
    o = flow.order("10")
    r = s.patch(f"/orders/{o['id']}", {"items": [{"product_id": ids["brk"], "quantity": "999"}]})
    assert r.status_code == 422
    assert s.patch(f"/orders/{o['id']}", {"notes": "Call before delivery"}).json()["notes"] == "Call before delivery"


def test_draft_edit_recalculates(as_role, flow, ids):
    o = flow.order("10", confirm=False)
    r = as_role(Role.SALES).patch(f"/orders/{o['id']}", {"items": [{"product_id": ids["brk"], "quantity": "20"}]})
    assert D(r.json()["subtotal"]) == D("80.00")


def test_cancel_paths(as_role, flow):
    s, admin = as_role(Role.SALES), as_role(Role.ADMIN)
    o = flow.order("10")
    assert s.post(f"/orders/{o['id']}/cancel", {"reason": "Customer withdrew"}).json()["status"] == "CANCELLED"
    # In production: sales may not cancel; admin may only before production starts.
    o2 = flow.order("10")
    flow.job(o2, allocate=True, start=False)
    assert s.post(f"/orders/{o2['id']}/cancel", {"reason": "nope"}).status_code == 403
    r = admin.post(f"/orders/{o2['id']}/cancel", {"reason": "Customer withdrew"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    o3 = flow.order("10")
    flow.job(o3)
    assert admin.post(f"/orders/{o3['id']}/cancel", {"reason": "too late"}).status_code == 422


def test_reject_requires_admin(as_role, flow):
    o = flow.order("1", confirm=False)
    assert as_role(Role.SALES).post(f"/orders/{o['id']}/reject", {"reason": "credit hold"}).status_code == 403
    assert as_role(Role.ADMIN).post(f"/orders/{o['id']}/reject", {"reason": "credit hold"}).json()["status"] == "REJECTED"


def test_order_filters(as_role, flow, ids):
    o = flow.order("3", confirm=False)
    s = as_role(Role.SALES)
    assert any(x["id"] == o["id"] for x in s.get("/orders", params={"status": "DRAFT"}).json()["items"])
    assert s.get("/orders", params={"q": o["order_number"]}).json()["total"] == 1
    assert all(
        x["customer"]["id"] == ids["customer"] for x in s.get("/orders", params={"customer_id": ids["customer"]}).json()["items"]
    )
