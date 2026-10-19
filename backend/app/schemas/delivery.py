from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import DeliveryStatus
from app.schemas.common import ORM, Dec, PositiveQty


class DeliveryItemIn(BaseModel):
    order_item_id: int
    quantity: PositiveQty


class DeliveryCreate(BaseModel):
    order_id: int
    warehouse_id: int | None = None
    planned_dispatch_date: date | None = None
    carrier: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    items: list[DeliveryItemIn] = Field(min_length=1)


class DispatchIn(BaseModel):
    carrier: str = Field(min_length=2, max_length=120)
    tracking_number: str = Field(min_length=2, max_length=120)


class ConfirmDeliveryIn(BaseModel):
    received_by: str = Field(min_length=2, max_length=120)
    delivered_at: datetime | None = None
    proof_of_delivery_ref: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class FailDeliveryIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    return_to_stock: bool = True


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DeliveryItemOut(ORM):
    id: int
    order_item_id: int
    sku: str
    description: str
    quantity: Dec


class OrderRef(ORM):
    id: int
    order_number: str
    status: str


class DeliveryOut(ORM):
    id: int
    delivery_number: str
    order: OrderRef
    customer_name: str
    warehouse_id: int
    status: DeliveryStatus
    planned_dispatch_date: date | None
    dispatched_at: datetime | None
    delivered_at: datetime | None
    carrier: str | None
    tracking_number: str | None
    received_by: str | None
    proof_of_delivery_ref: str | None
    failure_reason: str | None
    notes: str | None
    items: list[DeliveryItemOut]
    created_at: datetime
    updated_at: datetime


class DispatchableLine(BaseModel):
    order_item_id: int
    sku: str
    description: str
    ordered: Dec
    approved: Dec
    allocated: Dec
    dispatchable: Dec


class DispatchableOrder(BaseModel):
    order_id: int
    order_number: str
    customer_name: str
    required_date: date | None
    lines: list[DispatchableLine]
