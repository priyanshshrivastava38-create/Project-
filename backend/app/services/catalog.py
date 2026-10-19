from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError
from app.models import Material, Product, ProductMaterial, ProductRouteStep, StageDefinition, Supplier, User
from app.schemas.catalog import MaterialCreate, MaterialUpdate, ProductCreate
from app.services import audit
from app.services.common import get_or_404

QUALITY_STAGE = "QUALITY_INSPECTION"


def material_stmt(q: str | None, category: str | None, supplier_id: int | None, active: bool | None):
    stmt = select(Material)
    if q:
        stmt = stmt.where(or_(Material.sku.ilike(f"%{q}%"), Material.name.ilike(f"%{q}%")))
    if category:
        stmt = stmt.where(Material.category == category)
    if supplier_id:
        stmt = stmt.where(Material.preferred_supplier_id == supplier_id)
    if active is not None:
        stmt = stmt.where(Material.is_active.is_(active))
    return stmt.order_by(Material.sku)


def create_material(db: Session, user: User, data: MaterialCreate) -> Material:
    if db.execute(select(Material.id).where(Material.sku == data.sku)).first():
        raise ConflictError(f"Material SKU {data.sku} already exists")
    if data.preferred_supplier_id:
        get_or_404(db, Supplier, data.preferred_supplier_id, "Supplier")
    m = Material(**data.model_dump())
    db.add(m)
    db.flush()
    audit.record(db, user, "material.create", "material", m.id, f"Created material {m.sku}")
    db.commit()
    return m


def update_material(db: Session, user: User, material_id: int, data: MaterialUpdate) -> Material:
    m = get_or_404(db, Material, material_id, "Material", lock=True)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("preferred_supplier_id"):
        get_or_404(db, Supplier, changes["preferred_supplier_id"], "Supplier")
    for k, v in changes.items():
        setattr(m, k, v)
    audit.record(db, user, "material.update", "material", m.id, f"Updated material {m.sku}", {"fields": sorted(changes)})
    db.commit()
    return m


def create_product(db: Session, user: User, data: ProductCreate) -> Product:
    if db.execute(select(Product.id).where(Product.sku == data.sku)).first():
        raise ConflictError(f"Product SKU {data.sku} already exists")
    codes = list(data.stage_codes)
    if len(codes) != len(set(codes)):
        raise BusinessRuleError("A stage may appear only once in a route")
    if QUALITY_STAGE in codes and codes[-1] != QUALITY_STAGE:
        raise BusinessRuleError("QUALITY_INSPECTION must be the last stage of the route")
    if QUALITY_STAGE not in codes:
        codes.append(QUALITY_STAGE)
    stages = {s.code: s for s in db.execute(select(StageDefinition).where(StageDefinition.code.in_(codes))).scalars()}
    missing = [c for c in codes if c not in stages or not stages[c].is_active]
    if missing:
        raise BusinessRuleError("Unknown or inactive stage codes", {"codes": missing})
    mat_ids = [m.material_id for m in data.materials]
    if len(mat_ids) != len(set(mat_ids)):
        raise BusinessRuleError("Each material may be listed once")
    for mid in mat_ids:
        get_or_404(db, Material, mid, "Material")
    p = Product(sku=data.sku, name=data.name, description=data.description, uom=data.uom, unit_price=data.unit_price)
    p.materials = [ProductMaterial(material_id=m.material_id, quantity_per_unit=m.quantity_per_unit) for m in data.materials]
    p.route = [ProductRouteStep(stage_id=stages[c].id, sequence=i + 1) for i, c in enumerate(codes)]
    db.add(p)
    db.flush()
    audit.record(db, user, "product.create", "product", p.id, f"Created product {p.sku}")
    db.commit()
    return p
