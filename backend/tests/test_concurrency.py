"""Concurrency: real parallel transactions on separate connections (committed, then cleaned up)."""

import threading
from decimal import Decimal as D

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.errors import AppError
from app.models import AuditLog, InventoryBalance, InventoryTransaction, Material, User, Warehouse
from app.models.enums import ItemType
from app.schemas.inventory import AdjustmentIn, ReceiptIn
from app.services import inventory


@pytest.fixture()
def material():
    with Session(engine) as db:
        m = Material(sku="CONC-TEST", name="Concurrency test material", category="Test", uom="KG")
        db.add(m)
        db.commit()
        admin = db.execute(select(User).where(User.role == "ADMIN")).scalars().first()
        wh = db.execute(select(Warehouse).where(Warehouse.code == "RM")).scalar_one()
        inventory.receive(db, admin, ReceiptIn(material_id=m.id, warehouse_id=wh.id, quantity=D("100")), None)
        db.commit()
        ids = (m.id, wh.id, admin.id)
    yield ids
    with Session(engine) as db:
        bal_ids = [b for b in db.execute(select(InventoryBalance.id).where(InventoryBalance.material_id == ids[0])).scalars()]
        db.execute(delete(InventoryTransaction).where(InventoryTransaction.balance_id.in_(bal_ids)))
        db.execute(delete(InventoryBalance).where(InventoryBalance.id.in_(bal_ids)))
        db.execute(delete(AuditLog).where(AuditLog.entity_type == "material", AuditLog.entity_id == ids[0]))
        db.execute(delete(Material).where(Material.id == ids[0]))
        db.commit()


def _run_parallel(n, fn):
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        with Session(engine) as db:
            barrier.wait()
            try:
                results[i] = fn(db)
                db.commit()
            except AppError as e:
                db.rollback()
                results[i] = e

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results


def test_competing_withdrawals_never_overdraw(material):
    mid, wh, uid = material

    def withdraw(db):
        user = db.get(User, uid)
        return inventory.adjust(
            db,
            user,
            AdjustmentIn(
                item_type=ItemType.MATERIAL, item_id=mid, warehouse_id=wh, quantity_delta=D("-60"), reason="concurrent pick"
            ),
            None,
        )

    results = _run_parallel(2, withdraw)
    assert sum(1 for r in results if isinstance(r, tuple)) == 1
    assert sum(1 for r in results if isinstance(r, AppError)) == 1
    with Session(engine) as db:
        bal = db.execute(select(InventoryBalance).where(InventoryBalance.material_id == mid)).unique().scalar_one()
        assert bal.on_hand == D("40")
        assert all(r["ok"] for r in inventory.reconcile(db) if r["balance_id"] == bal.id)


def test_concurrent_duplicate_receipts_create_one_movement(material):
    mid, wh, uid = material

    def receive(db):
        user = db.get(User, uid)
        return inventory.receive(db, user, ReceiptIn(material_id=mid, warehouse_id=wh, quantity=D("25")), "dup-key-concurrency")

    results = _run_parallel(4, receive)
    created = [r for r in results if isinstance(r, tuple) and r[1]]
    assert len(created) == 1
    with Session(engine) as db:
        bal = db.execute(select(InventoryBalance).where(InventoryBalance.material_id == mid)).unique().scalar_one()
        assert bal.on_hand == D("125")
        n = (
            db.execute(select(InventoryTransaction).where(InventoryTransaction.idempotency_key == "dup-key-concurrency"))
            .unique()
            .all()
        )
        assert len(n) == 1
