from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Qty


class QualityInspection(Base):
    """An immutable inspection record. Corrections create a reinspection linked by parent_id."""

    __tablename__ = "quality_inspections"
    __table_args__ = (
        CheckConstraint("quantity_inspected > 0", name="ck_insp_qty_positive"),
        CheckConstraint("defect_quantity >= 0 AND defect_quantity <= quantity_inspected", name="ck_insp_defects"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_number: Mapped[str] = mapped_column(String(20), unique=True)
    production_job_id: Mapped[int] = mapped_column(ForeignKey("production_jobs.id", ondelete="RESTRICT"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("quality_inspections.id", ondelete="RESTRICT"))
    batch_ref: Mapped[str | None] = mapped_column(String(40))
    inspector_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quantity_inspected: Mapped[Decimal] = mapped_column(Qty)
    approved_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    defect_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    defect_description: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(8), index=True)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    reinspected: Mapped[bool] = mapped_column(default=False)

    job = relationship("ProductionJob", lazy="joined")
    inspector = relationship("User", lazy="joined")
