from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Money, Qty, TimestampMixin
from app.models.enums import OrderStatus


class CustomerOrder(TimestampMixin, Base):
    __tablename__ = "customer_orders"
    __table_args__ = (CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_order_tax_rate"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    required_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default=OrderStatus.DRAFT, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    tax_rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    customer = relationship("Customer", lazy="joined")
    created_by = relationship("User", lazy="joined")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.line_number", lazy="selectin"
    )
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.id", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_item_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_item_price_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    sku: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(Money)
    line_total: Mapped[Decimal] = mapped_column(Money)
    delivered_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))

    order = relationship("CustomerOrder", back_populates="items")
    product = relationship("Product", lazy="joined")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order = relationship("CustomerOrder", back_populates="history")
    changed_by = relationship("User", lazy="joined")
