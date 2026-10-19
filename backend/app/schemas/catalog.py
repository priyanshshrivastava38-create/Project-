from pydantic import BaseModel, Field

from app.schemas.common import ORM, Dec, NonNegQty, PositiveQty


class SupplierRef(ORM):
    id: int
    company_name: str


class MaterialBase(BaseModel):
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9\-_.]*$")
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=60)
    grade: str | None = Field(default=None, max_length=80)
    uom: str = Field(min_length=1, max_length=12)
    reorder_level: NonNegQty = 0
    preferred_supplier_id: int | None = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    grade: str | None = Field(default=None, max_length=80)
    reorder_level: NonNegQty | None = None
    preferred_supplier_id: int | None = None
    is_active: bool | None = None


class MaterialOut(ORM):
    id: int
    sku: str
    name: str
    category: str
    grade: str | None
    uom: str
    reorder_level: Dec
    preferred_supplier: SupplierRef | None
    is_active: bool


class MaterialRequirementIn(BaseModel):
    material_id: int
    quantity_per_unit: PositiveQty


class MaterialRequirementOut(ORM):
    material_id: int
    material: MaterialOut
    quantity_per_unit: Dec


class StageOut(ORM):
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool


class RouteStepOut(ORM):
    sequence: int
    stage: StageOut


class ProductCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9\-_.]*$")
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    uom: str = Field(default="EA", max_length=12)
    unit_price: Dec = Field(ge=0, max_digits=14, decimal_places=2)
    materials: list[MaterialRequirementIn] = Field(min_length=1)
    stage_codes: list[str] = Field(min_length=1, description="Ordered production route")


class ProductOut(ORM):
    id: int
    sku: str
    name: str
    description: str | None
    uom: str
    unit_price: Dec
    is_active: bool
    materials: list[MaterialRequirementOut]
    route: list[RouteStepOut]


class WarehouseOut(ORM):
    id: int
    code: str
    name: str
    address: str | None
    is_active: bool
