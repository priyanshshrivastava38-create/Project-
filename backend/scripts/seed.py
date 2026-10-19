"""Seed realistic demo data through the real service layer (ledger stays consistent).

Usage:  python -m scripts.seed            (skips if users already exist)
Env:    DEMO_PASSWORD  password for all demo accounts (required when ENVIRONMENT=production)

Only for demos/local development. Completion timestamps of seeded jobs are back-dated so the
production trend chart has history; that is the only direct data manipulation here.
"""

import os
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import ProductionJob, StageDefinition, User, Warehouse
from app.models.enums import InspectionOutcome
from app.permissions.policy import Role
from app.schemas.catalog import MaterialCreate, MaterialRequirementIn, ProductCreate
from app.schemas.delivery import ConfirmDeliveryIn, DeliveryCreate, DeliveryItemIn, DispatchIn
from app.schemas.inventory import ReceiptIn
from app.schemas.order import OrderCreate, OrderItemIn
from app.schemas.partner import CustomerCreate, SupplierCreate
from app.schemas.production import JobCreate, OutputIn
from app.schemas.quality import ChecklistItem, InspectionIn, ReinspectIn
from app.services import catalog, deliveries, documents, inventory, orders, partners, production, quality

TODAY = date.today()
USERS = [
    ("admin@metalflow.example", "Ava Admin", Role.ADMIN),
    ("sales@metalflow.example", "Sam Sales", Role.SALES),
    ("inventory@metalflow.example", "Ivan Inventory", Role.INVENTORY_MANAGER),
    ("production@metalflow.example", "Priya Production", Role.PRODUCTION_MANAGER),
    ("quality@metalflow.example", "Quinn Quality", Role.QUALITY_INSPECTOR),
    ("dispatch@metalflow.example", "Dana Dispatch", Role.DISPATCH),
    ("management@metalflow.example", "Morgan Management", Role.MANAGEMENT),
]
STAGES = [
    ("MATERIAL_PREP", "Material preparation"),
    ("CUTTING", "Cutting"),
    ("FORMING", "Forming"),
    ("MACHINING", "Machining"),
    ("WELDING", "Welding"),
    ("ASSEMBLY", "Assembly"),
    ("FINISHING", "Finishing"),
    ("QUALITY_INSPECTION", "Quality inspection"),
]
CHECKS = ["Dimensions within tolerance", "Surface finish", "Hole positions", "Coating thickness"]

QC_PROCEDURE = """# Quality Control Procedure QCP-01

## Purpose
This procedure defines how finished metal parts are inspected before they are released to finished-goods stock.

## Sampling
Each production batch is inspected. For batches up to 200 units, 100% visual inspection and a dimensional check of 20 units is required. For larger batches, a dimensional check of 32 units is required.

## Acceptance criteria
Dimensional tolerance is +/- 0.5 mm unless the drawing states otherwise. Powder coating thickness must be between 60 and 90 microns. Any crack, burr above 0.2 mm, or weld porosity is a defect.

## Failed inspections
If a batch fails, the good units are placed on hold and tagged with the inspection number. The production manager records the corrective action and the batch is reinspected. Defective units are scrapped and recorded as QC rejects. A failed batch must never be moved to finished goods.

## Records
Inspection records are kept for seven years and must not be altered; corrections are recorded as a new reinspection linked to the original.
"""

STEEL_SPEC = """# Steel Material Specification SPEC-MS-02

## Scope
Applies to mild steel sheet, plate and bar purchased for bracket, frame and shaft products.

## Material grade
Mild steel sheet and plate must be grade S275JR to EN 10025-2 or an approved equivalent (ASTM A36). Bar stock for machined shafts must be EN8 (080M40). Stainless panels use grade 304 (1.4301).

## Certification
Every delivery must be accompanied by a 3.1 mill certificate stating heat number, chemical composition and mechanical properties. Material without a certificate is quarantined and must not be received into available stock.

## Tolerances
Sheet thickness tolerance is +/- 0.15 mm for 3 mm sheet. Plate flatness must be within 3 mm per metre.

## Storage
Steel must be stored indoors on racks, off the floor, and separated by grade. Stainless steel must not contact carbon steel tooling to prevent contamination.
"""

PRICING_POLICY = """# Pricing and Discount Policy (Confidential)

## Discount authority
Sales staff may grant up to 5% discount. Discounts between 5% and 12% require management approval. Discounts above 12% require the managing director.

## Minimum margin
No order may be quoted below a 18% gross margin on material and labour cost.
"""

WELD_DRAFT = """# Welding Work Instruction WI-07 (DRAFT)

## Preheat
Preheat plate thicker than 25 mm to 100 C before welding.
"""


def main() -> None:
    settings = get_settings()
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        if settings.is_production:
            sys.exit("DEMO_PASSWORD must be set to seed a production environment")
        password = "MetalFlow-demo-2026"
    if len(password) < 10:
        sys.exit("DEMO_PASSWORD must be at least 10 characters")

    db = SessionLocal()
    try:
        if db.execute(select(User.id)).first():
            print("Database already has users; skipping seed.")
            return
        hashed = hash_password(password)
        users = {}
        for email, name, role in USERS:
            u = User(email=email, full_name=name, role=role, hashed_password=hashed, is_active=True)
            db.add(u)
            users[role] = u
        for code, name in STAGES:
            db.add(StageDefinition(code=code, name=name))
        rm = Warehouse(code="RM", name="Raw Material Store", address="Bay A, Plant 1")
        fg = Warehouse(code="FG", name="Finished Goods Warehouse", address="Bay D, Plant 1")
        yard = Warehouse(code="YARD", name="Steel Yard", address="Outdoor rack yard, Plant 1")
        db.add_all([rm, fg, yard])
        db.commit()
        admin, sales, inv, prod, qa, disp = (
            users[r]
            for r in (
                Role.ADMIN,
                Role.SALES,
                Role.INVENTORY_MANAGER,
                Role.PRODUCTION_MANAGER,
                Role.QUALITY_INSPECTOR,
                Role.DISPATCH,
            )
        )

        # Suppliers & materials
        sup = {}
        for name, contact, email in [
            ("Northern Steel Mills", "Harriet Cole", "orders@northernsteel.example"),
            ("Precision Fasteners Ltd", "Omar Siddiqui", "sales@precisionfasteners.example"),
            ("Allied Welding Supplies", "Grace Lin", "trade@alliedwelding.example"),
            ("Stainless Direct", "Marco Bianchi", "info@stainlessdirect.example"),
        ]:
            sup[name] = partners.create_supplier(
                db,
                admin,
                SupplierCreate(
                    company_name=name, contact_person=contact, email=email, phone="+44 161 555 0100", address="Industrial Estate"
                ),
            )
        mats = {}
        for sku, name, cat, grade, uom, reorder, supplier in [
            ("SHEET-MS-3MM", "Mild steel sheet 3 mm", "Sheet", "S275JR", "KG", "800", "Northern Steel Mills"),
            ("PLATE-MS-6MM", "Mild steel plate 6 mm", "Plate", "S275JR", "KG", "600", "Northern Steel Mills"),
            ("TUBE-SQ-40", "Square tube 40x40x3", "Tube", "S355J2H", "M", "300", "Northern Steel Mills"),
            ("BAR-EN8-40", "EN8 round bar 40 mm", "Bar", "EN8 / 080M40", "M", "120", "Northern Steel Mills"),
            ("SHEET-SS304-2MM", "Stainless sheet 2 mm", "Sheet", "304 / 1.4301", "KG", "400", "Stainless Direct"),
            ("BOLT-M8", "Hex bolt M8x25 zinc", "Fasteners", "Class 8.8", "EA", "2000", "Precision Fasteners Ltd"),
            ("WELD-WIRE-08", "MIG wire 0.8 mm", "Consumables", "ER70S-6", "KG", "50", "Allied Welding Supplies"),
            ("POWDER-BLK", "Powder coat black RAL9005", "Consumables", "Polyester", "KG", "40", "Allied Welding Supplies"),
        ]:
            mats[sku] = catalog.create_material(
                db,
                inv,
                MaterialCreate(
                    sku=sku,
                    name=name,
                    category=cat,
                    grade=grade,
                    uom=uom,
                    reorder_level=D(reorder),
                    preferred_supplier_id=sup[supplier].id,
                ),
            )
        partners.update_supplier(
            db,
            admin,
            sup["Northern Steel Mills"].id,
            partners.SupplierUpdate(
                material_ids=[mats[s].id for s in ("SHEET-MS-3MM", "PLATE-MS-6MM", "TUBE-SQ-40", "BAR-EN8-40")]
            ),
        )
        partners.update_supplier(
            db, admin, sup["Precision Fasteners Ltd"].id, partners.SupplierUpdate(material_ids=[mats["BOLT-M8"].id])
        )
        partners.update_supplier(
            db,
            admin,
            sup["Allied Welding Supplies"].id,
            partners.SupplierUpdate(material_ids=[mats["WELD-WIRE-08"].id, mats["POWDER-BLK"].id]),
        )
        partners.update_supplier(
            db, admin, sup["Stainless Direct"].id, partners.SupplierUpdate(material_ids=[mats["SHEET-SS304-2MM"].id])
        )

        # Products (single-level material requirements + routes)
        def req(sku, q):
            return MaterialRequirementIn(material_id=mats[sku].id, quantity_per_unit=D(q))

        products = {}
        for sku, name, price, reqs, route in [
            (
                "BRK-100",
                "Steel L-bracket 100 mm, powder coated",
                "4.20",
                [req("SHEET-MS-3MM", "0.45"), req("BOLT-M8", "2"), req("POWDER-BLK", "0.01")],
                ["MATERIAL_PREP", "CUTTING", "FORMING", "FINISHING", "QUALITY_INSPECTION"],
            ),
            (
                "FRM-200",
                "Welded frame assembly 1200x800",
                "185.00",
                [req("TUBE-SQ-40", "4.8"), req("PLATE-MS-6MM", "1.5"), req("WELD-WIRE-08", "0.12"), req("POWDER-BLK", "0.15")],
                ["MATERIAL_PREP", "CUTTING", "WELDING", "FINISHING", "QUALITY_INSPECTION"],
            ),
            (
                "SHF-300",
                "Machined drive shaft 40 mm x 320 mm",
                "38.50",
                [req("BAR-EN8-40", "0.35")],
                ["MATERIAL_PREP", "CUTTING", "MACHINING", "QUALITY_INSPECTION"],
            ),
            (
                "PNL-400",
                "Stainless access panel 600x400",
                "72.00",
                [req("SHEET-SS304-2MM", "2.1"), req("BOLT-M8", "4")],
                ["CUTTING", "FORMING", "FINISHING", "QUALITY_INSPECTION"],
            ),
        ]:
            products[sku] = catalog.create_product(
                db, admin, ProductCreate(sku=sku, name=name, unit_price=D(price), materials=reqs, stage_codes=route)
            )

        # Stock receipts (through the ledger)
        for sku, wh, q in [
            ("SHEET-MS-3MM", rm, "1500"),
            ("SHEET-MS-3MM", yard, "300"),
            ("PLATE-MS-6MM", rm, "900"),
            ("TUBE-SQ-40", yard, "650"),
            ("BAR-EN8-40", rm, "95"),
            ("SHEET-SS304-2MM", rm, "520"),
            ("BOLT-M8", rm, "6000"),
            ("WELD-WIRE-08", rm, "60"),
            ("POWDER-BLK", rm, "70"),
        ]:
            inventory.receive(
                db,
                inv,
                ReceiptIn(
                    material_id=mats[sku].id,
                    warehouse_id=wh.id,
                    quantity=D(q),
                    supplier_id=mats[sku].preferred_supplier_id,
                    reference=f"PO-{sku[:4]}-{q}",
                ),
                None,
            )
            db.commit()

        # Customers
        cust = {}
        for name, contact, email, city in [
            ("Acme Construction Ltd", "John Carter", "purchasing@acmeconstruction.example", "Leeds"),
            ("Brightline Shopfitting", "Emma Reid", "emma.reid@brightline.example", "Manchester"),
            ("Coastal Marine Engineering", "Liam O'Neill", "procurement@coastalmarine.example", "Hull"),
            ("Delta Agricultural Machinery", "Sofia Rossi", "buying@deltaagri.example", "York"),
            ("Evergreen Solar Mounts", "Noah Patel", "supply@evergreensolar.example", "Sheffield"),
        ]:
            cust[name] = partners.create_customer(
                db,
                sales,
                CustomerCreate(
                    company_name=name,
                    contact_person=contact,
                    email=email,
                    phone="+44 113 555 0199",
                    billing_address=f"1 Commerce Way, {city}",
                    shipping_address=f"Goods In, Unit 4, {city}",
                    tax_id=None,
                ),
            )

        def make_order(customer, items, days_ago, due_in, notes=None, confirm=True):
            o = orders.create_order(
                db,
                sales,
                OrderCreate(
                    customer_id=cust[customer].id,
                    order_date=TODAY - timedelta(days=days_ago),
                    required_date=TODAY + timedelta(days=due_in),
                    tax_rate=D("20"),
                    notes=notes,
                    items=[OrderItemIn(product_id=products[s].id, quantity=D(q)) for s, q in items],
                ),
            )
            if confirm:
                orders.confirm_order(db, sales, o.id)
            return o

        def run_job(order, line_idx, *, target_days, stop_at=None, good=None, fail_first=False, backdate_days=None):
            item = order.items[line_idx]
            job = production.create_job(
                db,
                prod,
                JobCreate(
                    order_item_id=item.id, target_date=TODAY + timedelta(days=target_days), assigned_to="Cell 2 – Day shift"
                ),
            )
            if stop_at == "PLANNED":
                return job
            production.allocate(db, inv, job.id, None)
            if stop_at == "ALLOCATED":
                return job
            production.start_job(db, prod, job.id)
            job = db.get(ProductionJob, job.id)
            codes = [s.stage_code for s in job.stages]
            qty_total = good if good is not None else job.planned_quantity
            produced = False
            for code in codes[1:]:
                if code == "QUALITY_INSPECTION" and not produced:
                    production.record_output(
                        db,
                        prod,
                        job.id,
                        OutputIn(good_quantity=qty_total, scrap_quantity=(job.planned_quantity * D("0.02")).quantize(D("1"))),
                    )
                    produced = True
                production.advance_stage(db, prod, job.id, None)
                if stop_at == code:
                    break
            if stop_at and stop_at != "COMPLETE":
                return db.get(ProductionJob, job.id)
            chk = [ChecklistItem(check=c, passed=True) for c in CHECKS]
            if fail_first:
                first = quality.create_inspection(
                    db,
                    qa,
                    InspectionIn(
                        production_job_id=job.id,
                        quantity_inspected=qty_total,
                        defect_quantity=D("3"),
                        outcome=InspectionOutcome.FAIL,
                        checklist=[ChecklistItem(check="Coating thickness", passed=False, note="45 microns measured")] + chk[:3],
                        defect_description="Powder coat below 60 microns on 3 units; batch held",
                        corrective_action=None,
                    ),
                )
                quality.reinspect(
                    db,
                    qa,
                    first.id,
                    ReinspectIn(
                        outcome=InspectionOutcome.PASS,
                        checklist=chk,
                        corrective_action="Recoated batch, oven temperature recalibrated",
                    ),
                )
            else:
                quality.create_inspection(
                    db,
                    qa,
                    InspectionIn(
                        production_job_id=job.id,
                        quantity_inspected=qty_total,
                        defect_quantity=D("0"),
                        outcome=InspectionOutcome.PASS,
                        checklist=chk,
                    ),
                )
            job = db.get(ProductionJob, job.id)
            if job.approved_quantity < job.planned_quantity:
                short = job.planned_quantity - job.approved_quantity
                production.allocate(db, inv, job.id, None)
                production.record_output(db, prod, job.id, OutputIn(good_quantity=short))
                quality.create_inspection(
                    db,
                    qa,
                    InspectionIn(
                        production_job_id=job.id, quantity_inspected=short, outcome=InspectionOutcome.PASS, checklist=chk
                    ),
                )
            production.complete_job(db, prod, job.id)
            if backdate_days:
                when = datetime.now(UTC) - timedelta(days=backdate_days)
                db.execute(update(ProductionJob).where(ProductionJob.id == job.id).values(actual_completion_at=when))
                db.commit()
            return db.get(ProductionJob, job.id)

        def ship(order, lines, *, confirm=True):
            d = deliveries.create_delivery(
                db,
                disp,
                DeliveryCreate(
                    order_id=order.id,
                    planned_dispatch_date=TODAY,
                    items=[DeliveryItemIn(order_item_id=order.items[i].id, quantity=D(q)) for i, q in lines],
                ),
            )
            deliveries.mark_ready(db, disp, d.id)
            deliveries.dispatch(db, disp, d.id, DispatchIn(carrier="Northline Haulage", tracking_number=f"NLH{d.id:06d}"))
            if confirm:
                deliveries.confirm_delivery(
                    db, disp, d.id, ConfirmDeliveryIn(received_by="Goods-in clerk", proof_of_delivery_ref=f"POD-{d.id:05d}")
                )
            else:
                deliveries.mark_in_transit(db, disp, d.id)
            return d

        # SO-1001: the headline scenario – 500 steel brackets, in production at FORMING
        o1 = make_order("Acme Construction Ltd", [("BRK-100", "500")], 6, 14, "Site delivery, call 30 min ahead")
        run_job(o1, 0, target_days=10, stop_at="FORMING")
        # SO-1002: fully delivered frames
        o2 = make_order("Brightline Shopfitting", [("FRM-200", "20")], 30, -5)
        run_job(o2, 0, target_days=-8, backdate_days=9)
        ship(o2, [(0, "20")])
        # SO-1003: two lines, one shipped (partially fulfilled), shafts in QC with a failed batch on hold
        o3 = make_order("Coastal Marine Engineering", [("SHF-300", "120"), ("BRK-100", "300")], 20, 3)
        run_job(o3, 1, target_days=-2, fail_first=True, backdate_days=4)
        ship(o3, [(1, "300")])
        j3 = run_job(o3, 0, target_days=-1, stop_at="QUALITY_INSPECTION", good=D("100"))
        quality.create_inspection(
            db,
            qa,
            InspectionIn(
                production_job_id=j3.id,
                quantity_inspected=D("40"),
                defect_quantity=D("4"),
                outcome=InspectionOutcome.FAIL,
                checklist=[ChecklistItem(check="Dimensions within tolerance", passed=False, note="Ø40 h7 oversize")],
                defect_description="Bearing journal oversize by 0.03 mm on 4 shafts; batch held for re-grind",
            ),
        )
        # SO-1004: confirmed, awaiting production
        make_order("Delta Agricultural Machinery", [("FRM-200", "12"), ("SHF-300", "40")], 2, 21)
        # SO-1005: draft
        make_order("Evergreen Solar Mounts", [("BRK-100", "1200")], 0, 30, "Quote follow-up, awaiting PO", confirm=False)
        # SO-1006: stainless panels completed & ready for dispatch (QC approved, not yet shipped)
        o6 = make_order("Brightline Shopfitting", [("PNL-400", "60")], 12, 4)
        run_job(o6, 0, target_days=2, backdate_days=1)
        # SO-1007: frames, job planned only, overdue target
        o7 = make_order("Acme Construction Ltd", [("FRM-200", "8")], 15, -1)
        run_job(o7, 0, target_days=-3, stop_at="PLANNED")
        # SO-1008: brackets shipped and in transit
        o8 = make_order("Evergreen Solar Mounts", [("BRK-100", "200")], 18, 1)
        run_job(o8, 0, target_days=0, backdate_days=2)
        ship(o8, [(0, "200")], confirm=False)

        # Documents
        for title, dtype, body, roles, approve in [
            ("Quality Control Procedure QCP-01", "PROCEDURE", QC_PROCEDURE, [], True),
            ("Steel Material Specification SPEC-MS-02", "SPECIFICATION", STEEL_SPEC, [], True),
            ("Pricing and Discount Policy", "POLICY", PRICING_POLICY, ["ADMIN", "SALES", "MANAGEMENT"], True),
            ("Welding Work Instruction WI-07", "WORK_INSTRUCTION", WELD_DRAFT, [], False),
        ]:
            doc = documents.upload(
                db,
                admin,
                filename=title.lower().replace(" ", "-") + ".md",
                data=body.encode(),
                title=title,
                doc_type=dtype,
                allowed_roles=roles,
                document_id=None,
            )
            if approve:
                documents.approve(db, admin, doc.id, None, "Approved for use")

        print("Seed complete. Demo accounts (password from DEMO_PASSWORD or the dev default):")
        for email, _, role in USERS:
            print(f"  {role:<20} {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
