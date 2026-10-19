"""Test setup.

* Uses TEST_DATABASE_URL (default: local ``metalflow_test``); refuses anything not ending in ``_test``.
* Schema is built with the real Alembic migrations, once per session.
* A small committed base dataset (users per role, warehouses, materials, a product, a customer,
  stock) is created once; each test runs inside a transaction that is rolled back afterwards
  (services' commit() calls only release a SAVEPOINT).
"""

import os

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://localhost:5432/metalflow_test")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_PROVIDER"] = "none"

from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.database import engine, get_db  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Customer, Material, Product, StageDefinition, User, Warehouse  # noqa: E402
from app.permissions.policy import Role  # noqa: E402

PASSWORD = "Test-password-123"
assert TEST_DB.rsplit("/", 1)[-1].endswith("_test"), "Refusing to run tests against a non-test database"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")
    _seed_base()
    yield


def _seed_base() -> None:
    from app.schemas.catalog import MaterialRequirementIn, ProductCreate
    from app.schemas.inventory import ReceiptIn
    from app.services import catalog, inventory

    with Session(engine) as db:
        hashed = hash_password(PASSWORD)
        for role in Role:
            db.add(
                User(email=f"{role.lower()}@test.example", full_name=f"{role.title()} User", role=role, hashed_password=hashed)
            )
        db.add(
            User(email="inactive@test.example", full_name="Inactive", role=Role.SALES, hashed_password=hashed, is_active=False)
        )
        for code, name in [
            ("MATERIAL_PREP", "Material preparation"),
            ("CUTTING", "Cutting"),
            ("FORMING", "Forming"),
            ("WELDING", "Welding"),
            ("FINISHING", "Finishing"),
            ("QUALITY_INSPECTION", "Quality inspection"),
        ]:
            db.add(StageDefinition(code=code, name=name))
        db.add_all([Warehouse(code="RM", name="Raw materials"), Warehouse(code="FG", name="Finished goods")])
        db.add(Customer(code="CUST-T1", company_name="Test Customer Ltd", email="buyer@customer.example", status="ACTIVE"))
        db.add(Customer(code="CUST-T2", company_name="Dormant Customer", status="INACTIVE"))
        db.add_all(
            [
                Material(sku="SHEET", name="Steel sheet", category="Sheet", uom="KG", reorder_level=D("100")),
                Material(sku="BOLT", name="Bolt M8", category="Fasteners", uom="EA", reorder_level=D("50")),
                Material(sku="RARE", name="Rare alloy", category="Bar", uom="KG", reorder_level=D("10")),
            ]
        )
        db.commit()
        admin = db.query(User).filter_by(role=Role.ADMIN).first()
        sheet = db.query(Material).filter_by(sku="SHEET").one()
        bolt = db.query(Material).filter_by(sku="BOLT").one()
        rare = db.query(Material).filter_by(sku="RARE").one()
        catalog.create_product(
            db,
            admin,
            ProductCreate(
                sku="BRK",
                name="Bracket",
                unit_price=D("4.00"),
                materials=[
                    MaterialRequirementIn(material_id=sheet.id, quantity_per_unit=D("0.5")),
                    MaterialRequirementIn(material_id=bolt.id, quantity_per_unit=D("2")),
                ],
                stage_codes=["CUTTING", "FORMING", "QUALITY_INSPECTION"],
            ),
        )
        catalog.create_product(
            db,
            admin,
            ProductCreate(
                sku="SCARCE",
                name="Scarce part",
                unit_price=D("99.00"),
                materials=[MaterialRequirementIn(material_id=rare.id, quantity_per_unit=D("1"))],
                stage_codes=["CUTTING"],
            ),
        )
        rm = db.query(Warehouse).filter_by(code="RM").one()
        for m, q in [(sheet, "1000"), (bolt, "5000"), (rare, "5")]:
            inventory.receive(db, admin, ReceiptIn(material_id=m.id, warehouse_id=rm.id, quantity=D(q)), None)
        db.commit()


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    from app.core.ratelimit import login_limiter

    login_limiter.reset()
    yield
    login_limiter.reset()


@pytest.fixture()
def db():
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture()
def client(db):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class Api:
    """Thin wrapper: Api(client, token).post(path, json) -> response."""

    def __init__(self, client: TestClient, token: str | None) -> None:
        self.c, self.h = client, ({"Authorization": f"Bearer {token}"} if token else {})

    def get(self, path, **kw):
        return self.c.get("/api/v1" + path, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def post(self, path, json=None, **kw):
        return self.c.post("/api/v1" + path, json=json, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def patch(self, path, json=None, **kw):
        return self.c.patch("/api/v1" + path, json=json, headers={**self.h, **kw.pop("headers", {})}, **kw)


@pytest.fixture()
def as_role(client, db):
    def make(role: Role | str) -> Api:
        user = db.query(User).filter_by(role=str(role), is_active=True).first()
        token, _ = create_access_token(user.id, user.role)
        return Api(client, token)

    return make


@pytest.fixture()
def ids(db):
    """Lookup of base-data ids by natural key."""
    return {
        "customer": db.query(Customer).filter_by(code="CUST-T1").one().id,
        "inactive_customer": db.query(Customer).filter_by(code="CUST-T2").one().id,
        "brk": db.query(Product).filter_by(sku="BRK").one().id,
        "scarce": db.query(Product).filter_by(sku="SCARCE").one().id,
        "sheet": db.query(Material).filter_by(sku="SHEET").one().id,
        "bolt": db.query(Material).filter_by(sku="BOLT").one().id,
        "rare": db.query(Material).filter_by(sku="RARE").one().id,
        "rm": db.query(Warehouse).filter_by(code="RM").one().id,
        "fg": db.query(Warehouse).filter_by(code="FG").one().id,
    }


# ----------------------------------------------------------------------------- workflow helpers


class Flow:
    """Drives the business workflow through the API with the right role for each step."""

    def __init__(self, as_role, ids):
        self.r, self.ids = as_role, ids
        self.sales, self.inv = as_role(Role.SALES), as_role(Role.INVENTORY_MANAGER)
        self.prod, self.qa, self.disp = as_role(Role.PRODUCTION_MANAGER), as_role(Role.QUALITY_INSPECTOR), as_role(Role.DISPATCH)

    def order(self, qty="100", product="brk", confirm=True) -> dict:
        r = self.sales.post(
            "/orders",
            {
                "customer_id": self.ids["customer"],
                "tax_rate": "10",
                "items": [{"product_id": self.ids[product], "quantity": qty}],
            },
        )
        assert r.status_code == 201, r.text
        o = r.json()
        if confirm:
            r = self.sales.post(f"/orders/{o['id']}/confirm")
            assert r.status_code == 200, r.text
            o = r.json()
        return o

    def job(self, order: dict, allocate=True, start=True) -> dict:
        r = self.prod.post("/production/jobs", {"order_item_id": order["items"][0]["id"]})
        assert r.status_code == 201, r.text
        job = r.json()
        if allocate:
            r = self.inv.post(f"/production/jobs/{job['id']}/allocate-materials", {})
            assert r.status_code == 200, r.text
            job = r.json()
        if start:
            r = self.prod.post(f"/production/jobs/{job['id']}/start")
            assert r.status_code == 200, r.text
            job = r.json()
        return job

    def to_qc(self, job: dict, good: str | None = None, scrap: str = "0") -> dict:
        """Record output at the first stage and advance until QUALITY_INSPECTION."""
        r = self.prod.post(
            f"/production/jobs/{job['id']}/record-output",
            {"good_quantity": good or job["planned_quantity"], "scrap_quantity": scrap},
        )
        assert r.status_code == 201, r.text
        while True:
            j = self.prod.get(f"/production/jobs/{job['id']}").json()
            if j["current_stage"]["stage_code"] == "QUALITY_INSPECTION":
                return j
            r = self.prod.post(f"/production/jobs/{job['id']}/advance", {})
            assert r.status_code == 200, r.text

    def inspect(self, job: dict, qty: str, outcome="PASS", defects="0", **extra):
        body = {
            "production_job_id": job["id"],
            "quantity_inspected": qty,
            "defect_quantity": defects,
            "outcome": outcome,
            "checklist": [{"check": "Dimensions", "passed": outcome == "PASS"}],
            **extra,
        }
        if (outcome == "FAIL" or defects != "0") and "defect_description" not in extra:
            body["defect_description"] = "Out of tolerance"
        return self.qa.post("/quality/inspections", body)

    def completed_order(self, qty="100") -> tuple[dict, dict]:
        o = self.order(qty)
        j = self.to_qc(self.job(o))
        assert self.inspect(j, qty).status_code == 201
        r = self.prod.post(f"/production/jobs/{j['id']}/complete")
        assert r.status_code == 200, r.text
        return self.sales.get(f"/orders/{o['id']}").json(), r.json()


@pytest.fixture()
def flow(as_role, ids):
    return Flow(as_role, ids)
