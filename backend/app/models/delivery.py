from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Qty, TimestampMixin
from app.models.enums import DeliveryStatus


class Delivery(TimestampMixin, Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_number: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(24), default=DeliveryStatus.PENDING, index=True)
    planned_dispatch_date: Mapped[date | None] = mapped_column(Date)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    carrier: Mapped[str | None] = mapped_column(String(120))
    tracking_number: Mapped[str | None] = mapped_column(String(120))
    received_by: Mapped[str | None] = mapped_column(String(120))
    proof_of_delivery_ref: Mapped[str | None] = mapped_column(String(200))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    order = relationship("CustomerOrder", lazy="joined")
    warehouse = relationship("Warehouse", lazy="joined")
    items: Mapped[list["DeliveryItem"]] = relationship(back_populates="delivery", cascade="all, delete-orphan", lazy="selectin")


class DeliveryItem(Base):
    __tablename__ = "delivery_items"
    __table_args__ = (
        UniqueConstraint("delivery_id", "order_item_id"),
        CheckConstraint("quantity > 0", name="ck_delivery_item_qty_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Qty)

    delivery = relationship("Delivery", back_populates="items")
    order_item = relationship("OrderItem", lazy="joined")
