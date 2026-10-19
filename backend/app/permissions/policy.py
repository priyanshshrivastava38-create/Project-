"""Role-based access control policy.

Permissions are checked server-side on every protected route via
``require_permission``. The frontend uses the same list (returned from
``/auth/me``) only to decide what to display.
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    SALES = "SALES"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER"
    QUALITY_INSPECTOR = "QUALITY_INSPECTOR"
    DISPATCH = "DISPATCH"
    MANAGEMENT = "MANAGEMENT"


class P(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    REPORTS_READ = "reports:read"
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    SUPPLIERS_READ = "suppliers:read"
    SUPPLIERS_WRITE = "suppliers:write"
    PRODUCTS_READ = "products:read"
    PRODUCTS_WRITE = "products:write"
    ORDERS_READ = "orders:read"
    ORDERS_WRITE = "orders:write"
    ORDERS_REJECT = "orders:reject"
    ORDERS_CANCEL_IN_PRODUCTION = "orders:cancel_in_production"
    INVENTORY_READ = "inventory:read"
    INVENTORY_RECEIVE = "inventory:receive"
    INVENTORY_ADJUST = "inventory:adjust"
    INVENTORY_RESERVE = "inventory:reserve"
    MATERIALS_WRITE = "materials:write"
    PRODUCTION_READ = "production:read"
    PRODUCTION_WRITE = "production:write"
    QUALITY_READ = "quality:read"
    QUALITY_WRITE = "quality:write"
    DELIVERIES_READ = "deliveries:read"
    DELIVERIES_WRITE = "deliveries:write"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_APPROVE = "documents:approve"
    ASSISTANT_USE = "assistant:use"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"


_READ_OPS = {
    P.DASHBOARD_READ,
    P.REPORTS_READ,
    P.CUSTOMERS_READ,
    P.SUPPLIERS_READ,
    P.PRODUCTS_READ,
    P.ORDERS_READ,
    P.INVENTORY_READ,
    P.PRODUCTION_READ,
    P.QUALITY_READ,
    P.DELIVERIES_READ,
    P.DOCUMENTS_READ,
    P.ASSISTANT_USE,
}

ROLE_PERMISSIONS: dict[Role, frozenset[P]] = {
    Role.ADMIN: frozenset(P),
    Role.MANAGEMENT: frozenset(_READ_OPS),
    Role.SALES: frozenset(
        {
            P.DASHBOARD_READ,
            P.REPORTS_READ,
            P.CUSTOMERS_READ,
            P.CUSTOMERS_WRITE,
            P.PRODUCTS_READ,
            P.ORDERS_READ,
            P.ORDERS_WRITE,
            P.DELIVERIES_READ,
            P.PRODUCTION_READ,
            P.DOCUMENTS_READ,
            P.ASSISTANT_USE,
        }
    ),
    Role.INVENTORY_MANAGER: frozenset(
        {
            P.DASHBOARD_READ,
            P.REPORTS_READ,
            P.SUPPLIERS_READ,
            P.SUPPLIERS_WRITE,
            P.PRODUCTS_READ,
            P.INVENTORY_READ,
            P.INVENTORY_RECEIVE,
            P.INVENTORY_ADJUST,
            P.INVENTORY_RESERVE,
            P.MATERIALS_WRITE,
            P.PRODUCTION_READ,
            P.ORDERS_READ,
            P.DOCUMENTS_READ,
            P.ASSISTANT_USE,
        }
    ),
    Role.PRODUCTION_MANAGER: frozenset(
        {
            P.DASHBOARD_READ,
            P.REPORTS_READ,
            P.PRODUCTS_READ,
            P.ORDERS_READ,
            P.INVENTORY_READ,
            P.INVENTORY_RESERVE,
            P.PRODUCTION_READ,
            P.PRODUCTION_WRITE,
            P.QUALITY_READ,
            P.DOCUMENTS_READ,
            P.DOCUMENTS_UPLOAD,
            P.ASSISTANT_USE,
        }
    ),
    Role.QUALITY_INSPECTOR: frozenset(
        {
            P.DASHBOARD_READ,
            P.PRODUCTS_READ,
            P.PRODUCTION_READ,
            P.QUALITY_READ,
            P.QUALITY_WRITE,
            P.ORDERS_READ,
            P.DOCUMENTS_READ,
            P.DOCUMENTS_UPLOAD,
            P.ASSISTANT_USE,
        }
    ),
    Role.DISPATCH: frozenset(
        {
            P.DASHBOARD_READ,
            P.ORDERS_READ,
            P.CUSTOMERS_READ,
            P.PRODUCTS_READ,
            P.INVENTORY_READ,
            P.DELIVERIES_READ,
            P.DELIVERIES_WRITE,
            P.DOCUMENTS_READ,
            P.ASSISTANT_USE,
        }
    ),
}


def has_permission(role: str | Role, permission: P) -> bool:
    try:
        return permission in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False


def permissions_for(role: str | Role) -> list[str]:
    return sorted(p.value for p in ROLE_PERMISSIONS.get(Role(role), frozenset()))
