from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

T = TypeVar("T")

# Decimals are serialised as JSON numbers-in-strings to avoid float rounding on the client.
Dec = Annotated[Decimal, PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json")]
PositiveQty = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
NonNegQty = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    ) -> None:
        self.page = page
        self.page_size = page_size


class Message(BaseModel):
    message: str


class UserRef(ORM):
    id: int
    full_name: str
