from decimal import ROUND_HALF_UP, Decimal
from typing import TypeVar

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError

T = TypeVar("T")
CENT = Decimal("0.01")
MILLI = Decimal("0.001")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def qty(v: Decimal) -> Decimal:
    return v.quantize(MILLI, rounding=ROUND_HALF_UP)


def get_or_404(db: Session, model: type[T], obj_id: int, label: str | None = None, lock: bool = False) -> T:
    if lock:
        obj = (
            db.execute(
                select(model).where(model.id == obj_id).with_for_update(of=model).execution_options(populate_existing=True)
            )
            .unique()
            .scalar_one_or_none()
        )
    else:
        obj = db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label or model.__name__} {obj_id} not found")
    return obj


def next_number(db: Session, sequence: str, prefix: str, width: int = 0) -> str:
    n = db.execute(text(f"SELECT nextval('{sequence}')")).scalar_one()
    return f"{prefix}{str(n).zfill(width)}"


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> tuple[list, int]:
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).unique().scalars().all()
    return list(rows), total
