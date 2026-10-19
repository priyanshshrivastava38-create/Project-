from decimal import Decimal as D

from app.permissions.policy import Role


def fg_on_hand(as_role):
    return sum(D(b["on_hand"]) for b in as_role(Role.ADMIN).get("/inventory", params={"item_type": "PRODUCT"}).json()["items"])


def test_cannot_ship_before_qc_approval(flow):
    o = flow.order("10")
    flow.to_qc(flow.job(o))
    r = flow.disp.post("/deliveries", {"order_id": o["id"], "items": [{"order_item_id": o["items"][0]["id"], "quantity": "1"}]})
    assert r.status_code == 422


def test_cannot_ship_beyond_approved_quantity(flow):
    order, _ = flow.completed_order("30")
    line = order["items"][0]["id"]
    r = flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "31"}]})
    assert r.status_code == 422
    assert (
        flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "20"}]}).status_code
        == 201
    )
    r = flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "11"}]})
    assert r.status_code == 422  # 20 already allocated; only 10 left


def test_full_dispatch_flow_with_partial_fulfillment(flow, as_role):
    order, _ = flow.completed_order("30")
    line = order["items"][0]["id"]
    fg0 = fg_on_hand(as_role)
    d = flow.disp.post(
        "/deliveries", {"order_id": order["id"], "carrier": "Northline", "items": [{"order_item_id": line, "quantity": "20"}]}
    ).json()
    assert d["status"] == "PENDING"
    # cannot dispatch before ready
    assert flow.disp.post(f"/deliveries/{d['id']}/dispatch", {"carrier": "Northline", "tracking_number": "T1"}).status_code == 422
    assert flow.disp.post(f"/deliveries/{d['id']}/ready").json()["status"] == "READY_FOR_DISPATCH"
    r = flow.disp.post(f"/deliveries/{d['id']}/dispatch", {"carrier": "Northline", "tracking_number": "T1"})
    assert r.status_code == 200 and r.json()["status"] == "DISPATCHED"
    # duplicate dispatch request does not move stock twice
    dup = flow.disp.post(f"/deliveries/{d['id']}/dispatch", {"carrier": "Northline", "tracking_number": "T1"})
    assert dup.status_code == 422
    assert fg_on_hand(as_role) == fg0 - 20
    txns = (
        as_role(Role.ADMIN)
        .get("/inventory/transactions", params={"txn_type": "DISPATCH", "reference_type": "DELIVERY", "reference_id": d["id"]})
        .json()
    )
    assert txns["total"] == 1
    # delivery confirmation needs a receiver
    assert flow.disp.post(f"/deliveries/{d['id']}/confirm-delivery", {}).status_code == 422
    assert flow.disp.post(f"/deliveries/{d['id']}/in-transit").json()["status"] == "IN_TRANSIT"
    c = flow.disp.post(f"/deliveries/{d['id']}/confirm-delivery", {"received_by": "J. Smith", "proof_of_delivery_ref": "POD-1"})
    assert c.status_code == 200 and c.json()["status"] == "DELIVERED"
    o = flow.sales.get(f"/orders/{order['id']}").json()
    assert o["status"] == "PARTIALLY_FULFILLED" and D(o["items"][0]["delivered_quantity"]) == 20
    # remaining 10
    d2 = flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "10"}]}).json()
    flow.disp.post(f"/deliveries/{d2['id']}/ready")
    flow.disp.post(f"/deliveries/{d2['id']}/dispatch", {"carrier": "Northline", "tracking_number": "T2"})
    flow.disp.post(f"/deliveries/{d2['id']}/confirm-delivery", {"received_by": "J. Smith"})
    assert flow.sales.get(f"/orders/{order['id']}").json()["status"] == "FULFILLED"
    # nothing left to ship
    assert (
        flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "1"}]}).status_code
        == 422
    )


def test_cancel_releases_and_failed_delivery_returns_stock(flow, as_role):
    order, _ = flow.completed_order("10")
    line = order["items"][0]["id"]
    fg0 = fg_on_hand(as_role)
    d = flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "10"}]}).json()
    flow.disp.post(f"/deliveries/{d['id']}/ready")
    assert flow.disp.post(f"/deliveries/{d['id']}/cancel", {"reason": "truck unavailable"}).json()["status"] == "CANCELLED"
    d = flow.disp.post("/deliveries", {"order_id": order["id"], "items": [{"order_item_id": line, "quantity": "10"}]}).json()
    flow.disp.post(f"/deliveries/{d['id']}/ready")
    flow.disp.post(f"/deliveries/{d['id']}/dispatch", {"carrier": "XPO Freight", "tracking_number": "Y1"})
    assert fg_on_hand(as_role) == fg0 - 10
    f = flow.disp.post(f"/deliveries/{d['id']}/fail", {"reason": "Site closed", "return_to_stock": True})
    assert f.status_code == 200 and f.json()["status"] == "FAILED"
    assert fg_on_hand(as_role) == fg0
    assert flow.disp.post(f"/deliveries/{d['id']}/confirm-delivery", {"received_by": "x y"}).status_code == 422


def test_dispatchable_listing(flow):
    order, _ = flow.completed_order("10")
    rows = flow.disp.get("/deliveries/dispatchable").json()
    row = next(r for r in rows if r["order_id"] == order["id"])
    assert D(row["lines"][0]["dispatchable"]) == 10


def test_sales_cannot_dispatch(flow, as_role):
    order, _ = flow.completed_order("5")
    r = as_role(Role.SALES).post(
        "/deliveries", {"order_id": order["id"], "items": [{"order_item_id": order["items"][0]["id"], "quantity": "5"}]}
    )
    assert r.status_code == 403
