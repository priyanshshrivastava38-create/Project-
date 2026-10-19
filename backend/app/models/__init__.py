"""Import every model so Alembic autogenerate and relationship resolution see them."""

from app.models.audit import AuditLog
from app.models.catalog import Material, Product, ProductMaterial, ProductRouteStep, StageDefinition, Warehouse
from app.models.delivery import Delivery, DeliveryItem
from app.models.document import (
    AssistantQuery,
    Document,
    DocumentApproval,
    DocumentChunk,
    DocumentFile,
    DocumentVersion,
)
from app.models.inventory import InventoryBalance, InventoryTransaction, Reservation
from app.models.order import CustomerOrder, OrderItem, OrderStatusHistory
from app.models.partner import Customer, Supplier, supplier_materials
from app.models.production import JobStage, ProductionJob, ProductionOutput
from app.models.quality import QualityInspection
from app.models.user import RefreshToken, User

__all__ = [
    "AssistantQuery",
    "AuditLog",
    "Customer",
    "CustomerOrder",
    "Delivery",
    "DeliveryItem",
    "Document",
    "DocumentApproval",
    "DocumentChunk",
    "DocumentFile",
    "DocumentVersion",
    "InventoryBalance",
    "InventoryTransaction",
    "JobStage",
    "Material",
    "OrderItem",
    "OrderStatusHistory",
    "Product",
    "ProductMaterial",
    "ProductRouteStep",
    "ProductionJob",
    "ProductionOutput",
    "QualityInspection",
    "RefreshToken",
    "Reservation",
    "StageDefinition",
    "Supplier",
    "User",
    "Warehouse",
    "supplier_materials",
]
