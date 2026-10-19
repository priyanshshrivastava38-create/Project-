from decimal import Decimal as D

from app.permissions.policy import Role


def test_job_cannot_start_without_materials(flow):
    o = flow.order("10")
    job = flow.job(o, allocate=False, start=False)
    r = flow.prod.post(f"/production/jobs/{job['id']}/start")
    assert r.status_code == 422
    assert "not fully allocated" in r.json()["error"]["message"]


def test_job_creation_rules(flow, as_role):
    draft = flow.order("10", confirm=False)
    assert flow.prod.post("/production/jobs", {"order_item_id": draft["items"][0]["id"]}).status_code == 422
    o = flow.order("10")
    item = o["items"][0]["id"]
    assert flow.prod.post("/production/jobs", {"order_item_id": item, "planned_quantity": "11"}).status_code == 422
    assert flow.prod.post("/production/jobs", {"order_item_id": item, "planned_quantity": "6"}).status_code == 201
    assert as_role(Role.SALES).get(f"/orders/{o['id']}").json()["status"] == "IN_PRODUCTION"
    r = flow.prod.post("/production/jobs", {"order_item_id": item})  # defaults to remainder (4)
    assert D(r.json()["planned_quantity"]) == 4
    assert flow.prod.post("/production/jobs", {"order_item_id": item}).status_code == 422  # fully planned


def test_stage_progression_and_material_consumption(flow, ids):
    o = flow.order("100")
    job = flow.job(o)
    assert job["status"] == "IN_PROGRESS" and job["current_stage"]["stage_code"] == "CUTTING"
    sheet = next(m for m in job["materials"] if m["material_id"] == ids["sheet"])
    assert D(sheet["required"]) == 50 and D(sheet["allocated"]) >= 50  # 0.5 kg/unit, + scrap allowance
    # cannot reach QC without output
    assert flow.prod.post(f"/production/jobs/{job['id']}/advance", {}).status_code == 200  # -> FORMING
    r = flow.prod.post(f"/production/jobs/{job['id']}/advance", {})
    assert r.status_code == 422 and "output" in r.json()["error"]["message"]
    out = flow.prod.post(f"/production/jobs/{job['id']}/record-output", {"good_quantity": "98", "scrap_quantity": "2"})
    assert out.status_code == 201
    j = flow.prod.get(f"/production/jobs/{job['id']}").json()
    sheet = next(m for m in j["materials"] if m["material_id"] == ids["sheet"])
    assert D(sheet["consumed"]) == 50  # (98 + 2) * 0.5
    assert D(j["produced_quantity"]) == 98 and D(j["rejected_quantity"]) == 2
    # cannot exceed planned good output
    assert flow.prod.post(f"/production/jobs/{job['id']}/record-output", {"good_quantity": "3"}).status_code == 422
    assert (
        flow.prod.post(f"/production/jobs/{job['id']}/advance", {}).json()["current_stage"]["stage_code"] == "QUALITY_INSPECTION"
    )
    assert flow.prod.post(f"/production/jobs/{job['id']}/advance", {}).status_code == 422  # final stage


def test_completion_requires_inspection(flow):
    o = flow.order("10")
    j = flow.to_qc(flow.job(o))
    r = flow.prod.post(f"/production/jobs/{j['id']}/complete")
    assert r.status_code == 422 and "awaiting inspection" in r.json()["error"]["message"]


def test_failed_inspection_blocks_finished_goods_then_reinspection(flow, as_role):
    o = flow.order("50")
    j = flow.to_qc(flow.job(o))
    inv = as_role(Role.INVENTORY_MANAGER)
    fg_before = sum(D(b["on_hand"]) for b in inv.get("/inventory", params={"item_type": "PRODUCT"}).json()["items"])
    fail = flow.inspect(j, "50", outcome="FAIL", defects="5")
    assert fail.status_code == 201
    insp = fail.json()
    assert insp["outcome"] == "FAIL" and D(insp["approved_quantity"]) == 0
    j = flow.prod.get(f"/production/jobs/{j['id']}").json()
    assert D(j["hold_quantity"]) == 45 and D(j["approved_quantity"]) == 0 and D(j["rejected_quantity"]) == 5
    fg_mid = sum(D(b["on_hand"]) for b in inv.get("/inventory", params={"item_type": "PRODUCT"}).json()["items"])
    assert fg_mid == fg_before  # failed units never reach finished goods
    assert flow.prod.post(f"/production/jobs/{j['id']}/complete").status_code == 422
    # Reinspection needs a corrective action; original record is preserved.
    assert flow.qa.post(f"/quality/inspections/{insp['id']}/reinspect", {"outcome": "PASS"}).status_code == 422
    re = flow.qa.post(f"/quality/inspections/{insp['id']}/reinspect", {"outcome": "PASS", "corrective_action": "Reworked edges"})
    assert re.status_code == 201 and re.json()["parent_id"] == insp["id"] and D(re.json()["approved_quantity"]) == 45
    original = flow.qa.get(f"/quality/inspections/{insp['id']}").json()
    assert original["outcome"] == "FAIL" and original["reinspected"] is True and D(original["defect_quantity"]) == 5
    assert (
        flow.qa.post(
            f"/quality/inspections/{insp['id']}/reinspect", {"outcome": "PASS", "corrective_action": "again"}
        ).status_code
        == 422
    )
    fg_after = sum(D(b["on_hand"]) for b in inv.get("/inventory", params={"item_type": "PRODUCT"}).json()["items"])
    assert fg_after == fg_before + 45
    # 45 approved of 50 planned: allocate material for 5 replacements, produce, inspect, complete.
    assert flow.inv.post(f"/production/jobs/{j['id']}/allocate-materials", {}).status_code == 200
    assert flow.prod.post(f"/production/jobs/{j['id']}/record-output", {"good_quantity": "5"}).status_code == 201
    assert flow.inspect(j, "5").status_code == 201
    done = flow.prod.post(f"/production/jobs/{j['id']}/complete")
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED"
    assert as_role(Role.SALES).get(f"/orders/{o['id']}").json()["status"] == "IN_PRODUCTION"  # not auto-fulfilled


def test_inspection_rules(flow, as_role):
    o = flow.order("10")
    job = flow.job(o)
    assert flow.inspect(job, "10").status_code == 422  # not at QC stage yet
    j = flow.to_qc(job)
    assert flow.inspect(j, "11").status_code == 422  # more than pending
    assert (
        flow.qa.post(
            "/quality/inspections", {"production_job_id": j["id"], "quantity_inspected": "1", "outcome": "FAIL"}
        ).status_code
        == 422
    )  # fail needs description
    assert (
        as_role(Role.PRODUCTION_MANAGER)
        .post("/quality/inspections", {"production_job_id": j["id"], "quantity_inspected": "1", "outcome": "PASS"})
        .status_code
        == 403
    )
    ok = flow.inspect(j, "10", defects="1", defect_description="burr")
    assert ok.status_code == 201 and D(ok.json()["approved_quantity"]) == 9


def test_completion_releases_unused_material(flow, as_role, ids):
    _, job = flow.completed_order("20")
    assert all(r["status"] in ("CONSUMED", "RELEASED") for r in job["reservations"])
    assert D(job["actual_completion_at"] is not None)


def test_production_board_groups_by_stage(flow):
    o = flow.order("10")
    job = flow.job(o)
    board = flow.prod.get("/production/board").json()
    col = next(c for c in board if c["key"] == "CUTTING")
    assert any(j["id"] == job["id"] for j in col["jobs"])


def test_overdue_filter(flow):
    o = flow.order("10")
    job = flow.job(o, allocate=False, start=False)
    flow.prod.patch(f"/production/jobs/{job['id']}", {"target_date": "2020-01-01"})
    overdue = flow.prod.get("/production/jobs", params={"overdue": True}).json()["items"]
    assert any(j["id"] == job["id"] and j["is_overdue"] for j in overdue)
