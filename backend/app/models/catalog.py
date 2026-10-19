from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Money, Qty, TimestampMixin


class Material(TimestampMixin, Base):
    """Raw material (steel sheet, bar stock, fasteners, ...). Quantities are in ``uom``."""

    __tablename__ = "materials"
    __table_args__ = (CheckConstraint("reorder_level >= 0", name="ck_material_reorder_nonneg"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), index=True)
    grade: Mapped[str | None] = mapped_column(String(80))
    uom: Mapped[str] = mapped_column(String(12))
    reorder_level: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    preferred_supplier = relationship("Supplier", lazy="joined")


class Product(TimestampMixin, Base):
    """A manufactured item that can be ordered. Finished goods are counted in ``uom`` (usually EA)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    uom: Mapped[str] = mapped_column(String(12), default="EA")
    unit_price: Mapped[Decimal] = mapped_column(Money)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    materials: Mapped[list["ProductMaterial"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    route: Mapped[list["ProductRouteStep"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductRouteStep.sequence", lazy="selectin"
    )


class ProductMaterial(Base):
    """Single-level material requirement: ``quantity_per_unit`` of material per finished unit."""

    __tablename__ = "product_materials"
    __table_args__ = (
        UniqueConstraint("product_id", "material_id"),
        CheckConstraint("quantity_per_unit > 0", name="ck_pm_qty_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    quantity_per_unit: Mapped[Decimal] = mapped_column(Qty)

    product = relationship("Product", back_populates="materials")
    material = relationship("Material", lazy="joined")


class StageDefinition(Base):
    """Configurable production stage (cutting, welding, ...)."""

    __tablename__ = "stage_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductRouteStep(Base):
    """The ordered list of stages a product goes through."""

    __tablename__ = "product_route_steps"
    __table_args__ = (UniqueConstraint("product_id", "sequence"), UniqueConstraint("product_id", "stage_id"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    stage_id: Mapped[int] = mapped_column(ForeignKey("stage_definitions.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer)

    product = relationship("Product", back_populates="route")
    stage = relationship("StageDefinition", lazy="joined")


class Warehouse(TimestampMixin, Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
