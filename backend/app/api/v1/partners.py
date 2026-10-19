from fastapi import APIRouter, Depends

from app.core.deps import DB, require
from app.models import Supplier, User
from app.permissions.policy import P
from app.schemas.common import Page, PageParams
from app.schemas.partner import (
    CustomerCreate,
    CustomerDetail,
    CustomerOut,
    CustomerUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from app.services import partners as svc
from app.services.common import get_or_404, paginate

customers = APIRouter(prefix="/customers", tags=["customers"])
suppliers = APIRouter(prefix="/suppliers", tags=["suppliers"])


@customers.get("", response_model=Page[CustomerOut])
def list_customers(
    db: DB,
    pp: PageParams = Depends(),
    q: str | None = None,
    status: str | None = None,
    sort: str = "company_name",
    _: User = Depends(require(P.CUSTOMERS_READ)),
) -> dict:
    items, total = paginate(db, svc.customer_stmt(q, status, sort), pp.page, pp.page_size)
    return {"items": items, "total": total, "page": pp.page, "page_size": pp.page_size}


@customers.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, db: DB, user: User = Depends(require(P.CUSTOMERS_WRITE))):
    return svc.create_customer(db, user, body)


@customers.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: DB, _: User = Depends(require(P.CUSTOMERS_READ))):
    return svc.customer_detail(db, customer_id)


@customers.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, body: CustomerUpdate, db: DB, user: User = Depends(require(P.CUSTOMERS_WRITE))):
    """Set ``status`` to INACTIVE to deactivate (customers are never hard-deleted; order history is preserved)."""
    return svc.update_customer(db, user, customer_id, body)


@suppliers.get("", response_model=Page[SupplierOut])
def list_suppliers(
    db: DB,
    pp: PageParams = Depends(),
    q: str | None = None,
    status: str | None = None,
    sort: str = "company_name",
    _: User = Depends(require(P.SUPPLIERS_READ)),
) -> dict:
    items, total = paginate(db, svc.supplier_stmt(q, status, sort), pp.page, pp.page_size)
    return {"items": items, "total": total, "page": pp.page, "page_size": pp.page_size}


@suppliers.post("", response_model=SupplierOut, status_code=201)
def create_supplier(body: SupplierCreate, db: DB, user: User = Depends(require(P.SUPPLIERS_WRITE))):
    return svc.create_supplier(db, user, body)


@suppliers.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: DB, _: User = Depends(require(P.SUPPLIERS_READ))):
    return get_or_404(db, Supplier, supplier_id, "Supplier")


@suppliers.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, body: SupplierUpdate, db: DB, user: User = Depends(require(P.SUPPLIERS_WRITE))):
    return svc.update_supplier(db, user, supplier_id, body)
