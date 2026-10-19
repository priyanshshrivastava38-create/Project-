from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import RecordStatus
from app.schemas.common import ORM


class CustomerBase(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]{5,40}$")
    billing_address: str | None = Field(default=None, max_length=1000)
    shipping_address: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=50)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]{5,40}$")
    billing_address: str | None = Field(default=None, max_length=1000)
    shipping_address: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=50)
    status: RecordStatus | None = None


class CustomerOut(ORM, CustomerBase):
    id: int
    code: str
    email: str | None
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class CustomerDetail(CustomerOut):
    order_count: int
    open_order_count: int


class MaterialRef(ORM):
    id: int
    sku: str
    name: str


class SupplierBase(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]{5,40}$")
    address: str | None = Field(default=None, max_length=1000)


class SupplierCreate(SupplierBase):
    material_ids: list[int] = []


class SupplierUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-.\s]{5,40}$")
    address: str | None = Field(default=None, max_length=1000)
    status: RecordStatus | None = None
    material_ids: list[int] | None = None


class SupplierOut(ORM, SupplierBase):
    id: int
    code: str
    email: str | None
    status: RecordStatus
    materials: list[MaterialRef]
    created_at: datetime
    updated_at: datetime
