from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auth,
    catalog,
    dashboard,
    deliveries,
    documents,
    inventory,
    orders,
    partners,
    production,
    quality,
)

api_router = APIRouter(prefix="/api/v1")
for r in (
    auth.router,
    auth.users_router,
    partners.customers,
    partners.suppliers,
    catalog.router,
    orders.router,
    inventory.router,
    production.router,
    quality.router,
    deliveries.router,
    documents.router,
    assistant.router,
    dashboard.router,
):
    api_router.include_router(r)
