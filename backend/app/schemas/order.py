from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import OrderStatus
from app.schemas.common import ORM, Dec, PositiveQty, UserRef


class OrderItemIn(BaseModel):
    product_id: int
    quantity: PositiveQty
    unit_price: Dec | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2, description="Defaults to the product list price"
    )
    description: str | None = Field(default=None, max_length=300)


class OrderCreate(BaseModel):
    customer_id: int
    order_date: date | None = None
    required_date: date | None = None
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    tax_rate: Dec | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[OrderItemIn] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        ids = [i.product_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product may appear only once per order; combine the quantities")
        return items


class OrderUpdate(BaseModel):
    """Full edits are allowed only in DRAFT; afterwards only notes may change."""

    customer_id: int | None = None
    required_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    tax_rate: Dec | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[OrderItemIn] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[OrderItemIn] | None) -> list[OrderItemIn] | None:
        if items is not None:
            ids = [i.product_id for i in items]
            if len(ids) != len(set(ids)):
                raise ValueError("Each product may appear only once per order")
        return items


class StatusChange(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class OrderItemOut(ORM):
    id: int
    line_number: int
    product_id: int
    sku: str
    description: str
    quantity: Dec
    unit_price: Dec
    line_total: Dec
    delivered_quantity: Dec


class OrderItemProgress(OrderItemOut):
    planned_quantity: Dec
    approved_quantity: Dec
    allocated_to_deliveries: Dec


class StatusHistoryOut(ORM):
    from_status: OrderStatus | None
    to_status: OrderStatus
    reason: str | None
    changed_by: UserRef | None
    changed_at: datetime


class CustomerRef(ORM):
    id: int
    code: str
    company_name: str


class OrderSummary(ORM):
    id: int
    order_number: str
    customer: CustomerRef
    order_date: date
    required_date: date | None
    status: OrderStatus
    currency: str
    total: Dec
    created_at: datetime


class OrderOut(OrderSummary):
    tax_rate: Dec
    subtotal: Dec
    tax_amount: Dec
    notes: str | None
    created_by: UserRef | None
    updated_at: datetime
    items: list[OrderItemOut]
    history: list[StatusHistoryOut]


class JobRef(ORM):
    id: int
    job_number: str
    order_item_id: int
    status: str
    planned_quantity: Dec
    approved_quantity: Dec


class DeliveryRef(ORM):
    id: int
    delivery_number: str
    status: str


class OrderDetail(OrderOut):
    item_progress: list[OrderItemProgress]
    jobs: list[JobRef]
    deliveries: list[DeliveryRef]
