from decimal import Decimal as D

from app.permissions.policy import Role


def balance(api, material_id, warehouse_id):
    items = api.get("/inventory", params={"item_type": "MATERIAL", "page_size": 200}).json()["items"]
    return next(b for b in items if b["material"]["id"] == material_id and b["warehouse"]["id"] == warehouse_id)


def test_receipt_updates_balance_and_ledger(as_role, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    before = D(balance(inv, ids["sheet"], ids["rm"])["on_hand"])
    r = inv.post(
        "/inventory/receipts", {"material_id": ids["sheet"], "warehouse_id": ids["rm"], "quantity": "250.5", "reference": "PO-77"}
    )
    assert r.status_code == 201
    t = r.json()
    assert t["txn_type"] == "RECEIPT" and D(t["on_hand_delta"]) == D("250.5") and D(t["on_hand_after"]) == before + D("250.5")
    assert D(balance(inv, ids["sheet"], ids["rm"])["on_hand"]) == before + D("250.5")


def test_receipt_idempotency_key_prevents_duplicate_movement(as_role, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    body = {"material_id": ids["bolt"], "warehouse_id": ids["rm"], "quantity": "100"}
    h = {"Idempotency-Key": "receipt-abc-123"}
    first = inv.post("/inventory/receipts", body, headers=h)
    second = inv.post("/inventory/receipts", body, headers=h)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    txns = inv.get("/inventory/transactions", params={"txn_type": "RECEIPT", "material_id": ids["bolt"], "page_size": 200}).json()
    assert sum(1 for t in txns["items"] if t["id"] == first.json()["id"]) == 1
    # Same key for a different operation type is a conflict.
    adj = inv.post(
        "/inventory/adjustments",
        {
            "item_type": "MATERIAL",
            "item_id": ids["bolt"],
            "warehouse_id": ids["rm"],
            "quantity_delta": "1",
            "reason": "count fix",
        },
        headers=h,
    )
    assert adj.status_code == 409


def test_adjustment_requires_reason_and_cannot_go_negative(as_role, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    base = {"item_type": "MATERIAL", "item_id": ids["rare"], "warehouse_id": ids["rm"]}
    assert inv.post("/inventory/adjustments", {**base, "quantity_delta": "-1"}).status_code == 422  # no reason
    assert inv.post("/inventory/adjustments", {**base, "quantity_delta": "0", "reason": "zero change"}).status_code == 422
    r = inv.post("/inventory/adjustments", {**base, "quantity_delta": "-500", "reason": "write-off attempt"})
    assert r.status_code == 422
    ok = inv.post("/inventory/adjustments", {**base, "quantity_delta": "-1", "reason": "damaged in handling"})
    assert ok.status_code == 201 and ok.json()["reason"] == "damaged in handling"


def test_reservation_cannot_exceed_available(as_role, flow, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    o = flow.order("4", product="scarce")
    job = flow.job(o, allocate=False, start=False)
    r = inv.post(
        "/inventory/reservations",
        {"production_job_id": job["id"], "material_id": ids["rare"], "warehouse_id": ids["rm"], "quantity": "6"},
    )
    assert r.status_code == 422  # only 5 on hand, and exceeds requirement
    o2 = flow.order("10", product="scarce")
    job2 = flow.job(o2, allocate=False, start=False)
    r = inv.post(f"/production/jobs/{job2['id']}/allocate-materials", {})
    assert r.status_code == 422 and r.json()["error"]["details"]["shortages"][0]["sku"] == "RARE"


def test_reserve_and_release(as_role, flow, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    o = flow.order("4", product="scarce")
    job = flow.job(o, allocate=False, start=False)
    before = balance(inv, ids["rare"], ids["rm"])
    r = inv.post(
        "/inventory/reservations",
        {"production_job_id": job["id"], "material_id": ids["rare"], "warehouse_id": ids["rm"], "quantity": "4"},
    )
    assert r.status_code == 201
    res = r.json()
    mid = balance(inv, ids["rare"], ids["rm"])
    assert D(mid["reserved"]) == D(before["reserved"]) + 4 and D(mid["available"]) == D(before["available"]) - 4
    # adjustment may not dip into reserved stock
    assert (
        inv.post(
            "/inventory/adjustments",
            {
                "item_type": "MATERIAL",
                "item_id": ids["rare"],
                "warehouse_id": ids["rm"],
                "quantity_delta": "-2",
                "reason": "count correction",
            },
        ).status_code
        == 422
    )
    rel = inv.post(f"/inventory/reservations/{res['id']}/release", {"reason": "plan changed"})
    assert rel.status_code == 200 and rel.json()["status"] == "RELEASED"
    assert D(balance(inv, ids["rare"], ids["rm"])["reserved"]) == D(before["reserved"])
    assert inv.post(f"/inventory/reservations/{res['id']}/release", {"reason": "again"}).status_code == 422


def test_ledger_reconciles(as_role, flow):
    flow.completed_order("20")
    rows = as_role(Role.ADMIN).get("/inventory/reconciliation").json()
    assert rows and all(r["ok"] for r in rows)


def test_low_stock_alerts(as_role, ids):
    inv = as_role(Role.INVENTORY_MANAGER)
    low = inv.get("/inventory/low-stock").json()
    assert any(m["sku"] == "RARE" for m in low)  # 5 on hand < reorder 10
    filtered = inv.get("/inventory", params={"low_stock": True}).json()["items"]
    assert filtered and all(b["low_stock"] for b in filtered)
