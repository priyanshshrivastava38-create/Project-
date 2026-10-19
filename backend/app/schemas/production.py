from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import JobPriority, JobStatus, StageStatus
from app.schemas.common import ORM, Dec, NonNegQty, PositiveQty
from app.schemas.inventory import ReservationOut


class JobCreate(BaseModel):
    order_item_id: int
    planned_quantity: PositiveQty | None = Field(default=None, description="Defaults to the unplanned remainder of the line")
    start_date: date | None = None
    target_date: date | None = None
    priority: JobPriority = JobPriority.NORMAL
    assigned_to: str | None = Field(default=None, max_length=120)
    output_warehouse_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def dates(self) -> "JobCreate":
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("target_date must be on or after start_date")
        return self


class JobUpdate(BaseModel):
    target_date: date | None = None
    priority: JobPriority | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class OutputIn(BaseModel):
    good_quantity: NonNegQty
    scrap_quantity: NonNegQty = 0
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def positive(self) -> "OutputIn":
        if self.good_quantity + self.scrap_quantity <= 0:
            raise ValueError("Report at least one good or scrapped unit")
        return self


class AdvanceIn(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


class AllocateIn(BaseModel):
    warehouse_id: int | None = Field(default=None, description="Restrict allocation to one warehouse")


class JobStageOut(ORM):
    sequence: int
    stage_code: str
    stage_name: str
    status: StageStatus
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None


class OutputOut(ORM):
    id: int
    batch_ref: str
    good_quantity: Dec
    scrap_quantity: Dec
    notes: str | None
    recorded_at: datetime


class ProductRef(ORM):
    id: int
    sku: str
    name: str
    uom: str


class OrderRef(ORM):
    id: int
    order_number: str
    status: str
    required_date: date | None


class JobSummary(ORM):
    id: int
    job_number: str
    order: OrderRef
    order_item_id: int
    product: ProductRef
    planned_quantity: Dec
    produced_quantity: Dec
    approved_quantity: Dec
    rejected_quantity: Dec
    pending_inspection_quantity: Dec
    hold_quantity: Dec
    status: JobStatus
    priority: JobPriority
    assigned_to: str | None
    start_date: date | None
    target_date: date | None
    actual_completion_at: datetime | None
    current_stage: JobStageOut | None
    is_overdue: bool = False


class MaterialRequirementStatus(BaseModel):
    material_id: int
    sku: str
    name: str
    uom: str
    required: Dec
    allocated: Dec
    consumed: Dec
    shortfall: Dec
    available_in_stock: Dec


class JobDetail(JobSummary):
    scrap_quantity: Dec
    qc_rejected_quantity: Dec
    started_at: datetime | None
    notes: str | None
    output_warehouse_id: int
    created_at: datetime
    stages: list[JobStageOut]
    outputs: list[OutputOut]
    materials: list[MaterialRequirementStatus]
    reservations: list[ReservationOut]
    materials_ready: bool
