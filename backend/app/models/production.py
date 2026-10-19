from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Qty, TimestampMixin
from app.models.enums import JobPriority, JobStatus, StageStatus


class ProductionJob(TimestampMixin, Base):
    """A work order producing ``planned_quantity`` of one order line.

    Quantity buckets (all in product uom):
      produced_quantity    good units reported by production (sent to QC)
      scrap_quantity       units scrapped during production
      approved_quantity    units that passed QC (moved to finished-goods stock)
      qc_rejected_quantity units rejected by QC
      hold_quantity        units from failed inspections awaiting rework/reinspection
      pending inspection = produced - approved - qc_rejected - hold
    """

    __tablename__ = "production_jobs"
    __table_args__ = (
        CheckConstraint("planned_quantity > 0", name="ck_job_planned_positive"),
        CheckConstraint(
            "produced_quantity >= approved_quantity + qc_rejected_quantity + hold_quantity",
            name="ck_job_qc_buckets",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_number: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="RESTRICT"), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    planned_quantity: Mapped[Decimal] = mapped_column(Qty)
    produced_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    scrap_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    approved_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qc_rejected_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    hold_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    actual_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(10), default=JobPriority.NORMAL)
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.PLANNED, index=True)
    current_stage_seq: Mapped[int] = mapped_column(Integer, default=1)
    output_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    order = relationship("CustomerOrder", lazy="joined")
    order_item = relationship("OrderItem", lazy="joined")
    product = relationship("Product", lazy="joined")
    stages: Mapped[list["JobStage"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStage.sequence", lazy="selectin"
    )
    outputs: Mapped[list["ProductionOutput"]] = relationship(
        back_populates="job", order_by="ProductionOutput.id", lazy="selectin"
    )

    @property
    def pending_inspection_quantity(self) -> Decimal:
        return self.produced_quantity - self.approved_quantity - self.qc_rejected_quantity - self.hold_quantity

    @property
    def rejected_quantity(self) -> Decimal:
        return self.scrap_quantity + self.qc_rejected_quantity

    @property
    def current_stage(self) -> "JobStage | None":
        return next((s for s in self.stages if s.sequence == self.current_stage_seq), None)


class JobStage(Base):
    """Snapshot of the product route for one job; doubles as stage history."""

    __tablename__ = "job_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("production_jobs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    stage_code: Mapped[str] = mapped_column(String(40))
    stage_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default=StageStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)

    job = relationship("ProductionJob", back_populates="stages")


class ProductionOutput(Base):
    """One output report (a batch). QC inspects batches by ``batch_ref``."""

    __tablename__ = "production_outputs"
    __table_args__ = (
        CheckConstraint("good_quantity >= 0 AND scrap_quantity >= 0", name="ck_output_nonneg"),
        CheckConstraint("good_quantity + scrap_quantity > 0", name="ck_output_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("production_jobs.id", ondelete="RESTRICT"), index=True)
    batch_ref: Mapped[str] = mapped_column(String(40), unique=True)
    good_quantity: Mapped[Decimal] = mapped_column(Qty)
    scrap_quantity: Mapped[Decimal] = mapped_column(Qty)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job = relationship("ProductionJob", back_populates="outputs")
