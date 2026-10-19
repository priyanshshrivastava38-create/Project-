from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError
from app.models import Customer, CustomerOrder, Material, Supplier, User
from app.models.enums import OrderStatus, RecordStatus
from app.schemas.partner import CustomerCreate, CustomerUpdate, SupplierCreate, SupplierUpdate
from app.services import audit
from app.services.common import get_or_404, next_number

CUSTOMER_SORTS = {"company_name": Customer.company_name, "created_at": Customer.created_at, "code": Customer.code}
SUPPLIER_SORTS = {"company_name": Supplier.company_name, "created_at": Supplier.created_at, "code": Supplier.code}
OPEN_ORDER_STATUSES = (OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.IN_PRODUCTION, OrderStatus.PARTIALLY_FULFILLED)


def _sort(cols: dict, sort: str):
    desc = sort.startswith("-")
    col = cols.get(sort.lstrip("-"))
    if col is None:
        raise BusinessRuleError(f"Unsupported sort field '{sort}'", {"allowed": list(cols)})
    return col.desc() if desc else col.asc()


def customer_stmt(q: str | None, status: str | None, sort: str):
    stmt = select(Customer)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Customer.company_name.ilike(like),
                Customer.code.ilike(like),
                Customer.contact_person.ilike(like),
                Customer.email.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(Customer.status == status)
    return stmt.order_by(_sort(CUSTOMER_SORTS, sort), Customer.id)


def _check_customer_unique(db: Session, company_name: str | None, email: str | None, exclude_id: int | None = None) -> None:
    if company_name:
        stmt = select(Customer.id).where(func.lower(Customer.company_name) == company_name.lower())
        if exclude_id:
            stmt = stmt.where(Customer.id != exclude_id)
        if db.execute(stmt).first():
            raise ConflictError(f"A customer named '{company_name}' already exists")
    if email:
        stmt = select(Customer.id).where(func.lower(Customer.email) == email.lower())
        if exclude_id:
            stmt = stmt.where(Customer.id != exclude_id)
        if db.execute(stmt).first():
            raise ConflictError(f"A customer with email '{email}' already exists")


def create_customer(db: Session, user: User, data: CustomerCreate) -> Customer:
    _check_customer_unique(db, data.company_name, data.email)
    c = Customer(**data.model_dump(), code=next_number(db, "customer_code_seq", "CUST-", 4))
    db.add(c)
    db.flush()
    audit.record(db, user, "customer.create", "customer", c.id, f"Created customer {c.code} {c.company_name}")
    db.commit()
    return c


def update_customer(db: Session, user: User, customer_id: int, data: CustomerUpdate) -> Customer:
    c = get_or_404(db, Customer, customer_id, "Customer", lock=True)
    changes = data.model_dump(exclude_unset=True)
    _check_customer_unique(db, changes.get("company_name"), changes.get("email"), exclude_id=c.id)
    if changes.get("status") == RecordStatus.INACTIVE:
        open_orders = db.execute(
            select(func.count()).where(CustomerOrder.customer_id == c.id, CustomerOrder.status.in_(OPEN_ORDER_STATUSES))
        ).scalar_one()
        if open_orders:
            raise BusinessRuleError(f"Customer has {open_orders} open order(s); close them before deactivating")
    for k, v in changes.items():
        setattr(c, k, v)
    audit.record(db, user, "customer.update", "customer", c.id, f"Updated customer {c.code}", {"fields": sorted(changes)})
    db.commit()
    return c


def customer_detail(db: Session, customer_id: int) -> dict:
    c = get_or_404(db, Customer, customer_id, "Customer")
    total = db.execute(select(func.count()).where(CustomerOrder.customer_id == c.id)).scalar_one()
    open_ = db.execute(
        select(func.count()).where(CustomerOrder.customer_id == c.id, CustomerOrder.status.in_(OPEN_ORDER_STATUSES))
    ).scalar_one()
    return {
        **{
            k: getattr(c, k)
            for k in (
                "id",
                "code",
                "company_name",
                "contact_person",
                "email",
                "phone",
                "billing_address",
                "shipping_address",
                "tax_id",
                "status",
                "created_at",
                "updated_at",
            )
        },
        "order_count": total,
        "open_order_count": open_,
    }


def supplier_stmt(q: str | None, status: str | None, sort: str):
    stmt = select(Supplier)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Supplier.company_name.ilike(like), Supplier.code.ilike(like), Supplier.contact_person.ilike(like)))
    if status:
        stmt = stmt.where(Supplier.status == status)
    return stmt.order_by(_sort(SUPPLIER_SORTS, sort), Supplier.id)


def _materials(db: Session, ids: list[int]) -> list[Material]:
    mats = list(db.execute(select(Material).where(Material.id.in_(ids))).unique().scalars()) if ids else []
    if len(mats) != len(set(ids)):
        raise BusinessRuleError("One or more material_ids do not exist")
    return mats


def create_supplier(db: Session, user: User, data: SupplierCreate) -> Supplier:
    if db.execute(select(Supplier.id).where(func.lower(Supplier.company_name) == data.company_name.lower())).first():
        raise ConflictError(f"A supplier named '{data.company_name}' already exists")
    s = Supplier(**data.model_dump(exclude={"material_ids"}), code=next_number(db, "supplier_code_seq", "SUP-", 4))
    s.materials = _materials(db, data.material_ids)
    db.add(s)
    db.flush()
    audit.record(db, user, "supplier.create", "supplier", s.id, f"Created supplier {s.code} {s.company_name}")
    db.commit()
    return s


def update_supplier(db: Session, user: User, supplier_id: int, data: SupplierUpdate) -> Supplier:
    s = get_or_404(db, Supplier, supplier_id, "Supplier", lock=True)
    changes = data.model_dump(exclude_unset=True)
    if (
        "company_name" in changes
        and db.execute(
            select(Supplier.id).where(func.lower(Supplier.company_name) == changes["company_name"].lower(), Supplier.id != s.id)
        ).first()
    ):
        raise ConflictError(f"A supplier named '{changes['company_name']}' already exists")
    if "material_ids" in changes:
        s.materials = _materials(db, changes.pop("material_ids") or [])
    for k, v in changes.items():
        setattr(s, k, v)
    audit.record(
        db,
        user,
        "supplier.update",
        "supplier",
        s.id,
        f"Updated supplier {s.code}",
        {"fields": sorted(data.model_dump(exclude_unset=True))},
    )
    db.commit()
    return s
