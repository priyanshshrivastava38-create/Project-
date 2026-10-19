from fastapi import APIRouter, Depends
from sqlalchemy import distinct, select

from app.core.deps import DB, require
from app.models import Material, Product, StageDefinition, User, Warehouse
from app.permissions.policy import P
from app.schemas.catalog import MaterialCreate, MaterialOut, MaterialUpdate, ProductCreate, ProductOut, StageOut, WarehouseOut
from app.schemas.common import Page, PageParams
from app.services import catalog as svc
from app.services.common import get_or_404, paginate

router = APIRouter(tags=["catalog"])


@router.get("/materials", response_model=Page[MaterialOut])
def list_materials(
    db: DB,
    pp: PageParams = Depends(),
    q: str | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    active: bool | None = None,
    _: User = Depends(require(P.PRODUCTS_READ)),
) -> dict:
    items, total = paginate(db, svc.material_stmt(q, category, supplier_id, active), pp.page, pp.page_size)
    return {"items": items, "total": total, "page": pp.page, "page_size": pp.page_size}


@router.get("/materials/categories", response_model=list[str])
def material_categories(db: DB, _: User = Depends(require(P.PRODUCTS_READ))) -> list[str]:
    return list(db.execute(select(distinct(Material.category)).order_by(Material.category)).scalars())


@router.post("/materials", response_model=MaterialOut, status_code=201)
def create_material(body: MaterialCreate, db: DB, user: User = Depends(require(P.MATERIALS_WRITE))):
    return svc.create_material(db, user, body)


@router.patch("/materials/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, body: MaterialUpdate, db: DB, user: User = Depends(require(P.MATERIALS_WRITE))):
    return svc.update_material(db, user, material_id, body)


@router.get("/products", response_model=list[ProductOut])
def list_products(db: DB, active: bool | None = True, _: User = Depends(require(P.PRODUCTS_READ))):
    stmt = select(Product).order_by(Product.sku)
    if active is not None:
        stmt = stmt.where(Product.is_active.is_(active))
    return list(db.execute(stmt).scalars())


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DB, _: User = Depends(require(P.PRODUCTS_READ))):
    return get_or_404(db, Product, product_id, "Product")


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: DB, user: User = Depends(require(P.PRODUCTS_WRITE))):
    return svc.create_product(db, user, body)


@router.get("/stages", response_model=list[StageOut])
def list_stages(db: DB, _: User = Depends(require(P.PRODUCTION_READ))):
    return list(db.execute(select(StageDefinition).order_by(StageDefinition.id)).scalars())


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(db: DB, _: User = Depends(require(P.INVENTORY_READ))):
    return list(db.execute(select(Warehouse).order_by(Warehouse.code)).scalars())
