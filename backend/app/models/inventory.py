from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Qty
from app.models.enums import ReservationStatus


class InventoryBalance(Base):
    """Current stock of one item in one warehouse.

    The balance is a cache of the ledger: on_hand == SUM(on_hand_delta) and
    reserved == SUM(reserved_delta) over inventory_transactions for this row.
    Only app.services.inventory mutates it, always under SELECT ... FOR UPDATE.
    """

    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("(material_id IS NULL) <> (product_id IS NULL)", name="ck_balance_one_item"),
        CheckConstraint("on_hand >= 0", name="ck_balance_on_hand_nonneg"),
        CheckConstraint("reserved >= 0", name="ck_balance_reserved_nonneg"),
        CheckConstraint("reserved <= on_hand", name="ck_balance_reserved_le_on_hand"),
        Index(
            "uq_balance_material_wh", "material_id", "warehouse_id", unique=True, postgresql_where=text("material_id IS NOT NULL")
        ),
        Index(
            "uq_balance_product_wh", "product_id", "warehouse_id", unique=True, postgresql_where=text("product_id IS NOT NULL")
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_type: Mapped[str] = mapped_column(String(16))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    on_hand: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    reserved: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    material = relationship("Material", lazy="joined")
    product = relationship("Product", lazy="joined")
    warehouse = relationship("Warehouse", lazy="joined")

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved


class InventoryTransaction(Base):
    """Append-only inventory ledger. Rows are never updated or deleted."""

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_txn_reference", "reference_type", "reference_id"),
        Index("uq_txn_idempotency", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance_id: Mapped[int] = mapped_column(ForeignKey("inventory_balances.id", ondelete="RESTRICT"), index=True)
    txn_type: Mapped[str] = mapped_column(String(16), index=True)
    on_hand_delta: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    reserved_delta: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    on_hand_after: Mapped[Decimal] = mapped_column(Qty)
    reserved_after: Mapped[Decimal] = mapped_column(Qty)
    reference_type: Mapped[str | None] = mapped_column(String(32))
    reference_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    balance = relationship("InventoryBalance", lazy="joined")
    user = relationship("User", lazy="joined")


class Reservation(Base):
    """Stock reserved for a production job (materials) or a delivery (finished goods)."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_res_qty_positive"),
        CheckConstraint("consumed_quantity >= 0 AND consumed_quantity <= quantity", name="ck_res_consumed_range"),
        CheckConstraint("(production_job_id IS NULL) <> (delivery_id IS NULL)", name="ck_res_one_owner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance_id: Mapped[int] = mapped_column(ForeignKey("inventory_balances.id", ondelete="RESTRICT"), index=True)
    production_job_id: Mapped[int | None] = mapped_column(ForeignKey("production_jobs.id", ondelete="RESTRICT"), index=True)
    delivery_id: Mapped[int | None] = mapped_column(ForeignKey("deliveries.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Qty)
    consumed_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), default=ReservationStatus.ACTIVE, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    balance = relationship("InventoryBalance", lazy="joined")

    @property
    def remaining(self) -> Decimal:
        return self.quantity - self.consumed_quantity
