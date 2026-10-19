from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ItemType, ReservationStatus, TxnType
from app.schemas.common import ORM, Dec, PositiveQty, UserRef


class ItemRef(ORM):
    id: int
    sku: str
    name: str
    uom: str


class WarehouseRef(ORM):
    id: int
    code: str
    name: str


class BalanceOut(ORM):
    id: int
    item_type: ItemType
    material: ItemRef | None
    product: ItemRef | None
    warehouse: WarehouseRef
    on_hand: Dec
    reserved: Dec
    available: Dec
    reorder_level: Dec | None = None
    category: str | None = None
    low_stock: bool = False
    updated_at: datetime


class TransactionOut(ORM):
    id: int
    txn_type: TxnType
    balance: BalanceOut
    on_hand_delta: Dec
    reserved_delta: Dec
    on_hand_after: Dec
    reserved_after: Dec
    reference_type: str | None
    reference_id: int | None
    reason: str | None
    user: UserRef | None
    created_at: datetime


class ReceiptIn(BaseModel):
    material_id: int
    warehouse_id: int
    quantity: PositiveQty
    supplier_id: int | None = None
    reference: str | None = Field(default=None, max_length=100, description="Supplier delivery note / PO number")
    notes: str | None = Field(default=None, max_length=500)


class AdjustmentIn(BaseModel):
    item_type: ItemType
    item_id: int
    warehouse_id: int
    quantity_delta: Dec = Field(max_digits=14, decimal_places=3, description="Positive adds stock, negative removes")
    reason: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def non_zero(self) -> "AdjustmentIn":
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta must not be zero")
        return self


class ReservationIn(BaseModel):
    production_job_id: int
    material_id: int
    warehouse_id: int
    quantity: PositiveQty


class ReservationOut(ORM):
    id: int
    balance: BalanceOut
    production_job_id: int | None
    delivery_id: int | None
    quantity: Dec
    consumed_quantity: Dec
    remaining: Dec
    status: ReservationStatus
    created_at: datetime
    closed_at: datetime | None


class ReconciliationRow(BaseModel):
    balance_id: int
    on_hand: Dec
    ledger_on_hand: Dec
    reserved: Dec
    ledger_reserved: Dec
    ok: bool
