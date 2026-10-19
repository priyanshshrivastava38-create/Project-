from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import RecordStatus

supplier_materials = Table(
    "supplier_materials",
    Base.metadata,
    Column("supplier_id", ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
    Column("material_id", ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    billing_address: Mapped[str | None] = mapped_column(Text)
    shipping_address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(16), default=RecordStatus.ACTIVE, index=True)


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    company_name: Mapped[str] = mapped_column(String(200), unique=True)
    contact_person: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=RecordStatus.ACTIVE, index=True)

    materials: Mapped[list["Material"]] = relationship(secondary=supplier_materials, lazy="selectin")  # noqa: F821
