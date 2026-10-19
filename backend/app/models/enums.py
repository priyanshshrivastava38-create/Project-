from enum import StrEnum


class RecordStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    IN_PRODUCTION = "IN_PRODUCTION"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ItemType(StrEnum):
    MATERIAL = "MATERIAL"
    PRODUCT = "PRODUCT"


class TxnType(StrEnum):
    RECEIPT = "RECEIPT"  # raw material received from supplier
    ADJUSTMENT = "ADJUSTMENT"  # authorised correction, reason mandatory
    RESERVE = "RESERVE"  # reserved qty up, on-hand unchanged
    RELEASE = "RELEASE"  # reserved qty down, on-hand unchanged
    CONSUME = "CONSUME"  # material used by production (on-hand and reserved down)
    PRODUCE = "PRODUCE"  # QC-approved finished goods into stock
    DISPATCH = "DISPATCH"  # finished goods shipped (on-hand and reserved down)
    RETURN = "RETURN"  # failed delivery returned to stock


class JobStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class JobPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class StageStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"


class InspectionOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DocumentStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
