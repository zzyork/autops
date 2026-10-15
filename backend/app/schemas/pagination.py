from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel, BeforeValidator

T = TypeVar("T")
MAX_PAGE = 1_000_000
DEFAULT_PAGE_SIZE = 10

PageNumber = Annotated[int | None, Query(ge=1, le=MAX_PAGE)]


def parse_page_size(value: str | int) -> str | int:
    return int(value) if isinstance(value, str) and value.isascii() and value.isdecimal() else value


PageSize = Annotated[Literal[10, 20, 50, 100], BeforeValidator(parse_page_size), Query()]


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
