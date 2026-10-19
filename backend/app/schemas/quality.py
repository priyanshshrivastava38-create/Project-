from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import InspectionOutcome
from app.schemas.common import ORM, Dec, NonNegQty, PositiveQty, UserRef


class ChecklistItem(BaseModel):
    check: str = Field(min_length=1, max_length=200)
    passed: bool
    note: str | None = Field(default=None, max_length=300)


class InspectionIn(BaseModel):
    production_job_id: int
    batch_ref: str | None = Field(default=None, max_length=40)
    quantity_inspected: PositiveQty
    defect_quantity: NonNegQty = 0
    outcome: InspectionOutcome
    checklist: list[ChecklistItem] = []
    defect_description: str | None = Field(default=None, max_length=2000)
    corrective_action: str | None = Field(default=None, max_length=2000)
    comments: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def rules(self) -> "InspectionIn":
        if self.defect_quantity > self.quantity_inspected:
            raise ValueError("defect_quantity cannot exceed quantity_inspected")
        if self.outcome == InspectionOutcome.FAIL and not self.defect_description:
            raise ValueError("A failed inspection requires a defect_description")
        if self.defect_quantity > 0 and not self.defect_description:
            raise ValueError("defect_description is required when defects are recorded")
        return self


class ReinspectIn(BaseModel):
    """Reinspects the full quantity held by the failed inspection."""

    defect_quantity: NonNegQty = 0
    outcome: InspectionOutcome
    checklist: list[ChecklistItem] = []
    defect_description: str | None = Field(default=None, max_length=2000)
    corrective_action: str = Field(min_length=3, max_length=2000, description="What was corrected before reinspection")
    comments: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def rules(self) -> "ReinspectIn":
        if self.outcome == InspectionOutcome.FAIL and not self.defect_description:
            raise ValueError("A failed inspection requires a defect_description")
        return self


class JobRef(ORM):
    id: int
    job_number: str
    order_id: int


class InspectionOut(ORM):
    id: int
    inspection_number: str
    job: JobRef
    order_number: str | None = None
    parent_id: int | None
    batch_ref: str | None
    inspector: UserRef | None
    inspected_at: datetime
    quantity_inspected: Dec
    approved_quantity: Dec
    defect_quantity: Dec
    checklist: list[ChecklistItem]
    defect_description: str | None
    outcome: InspectionOutcome
    corrective_action: str | None
    comments: str | None
    reinspected: bool
