from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def fetch_rows(session: Session, query: Select[tuple[T]], page: int | None,
               page_size: int, legacy_limit: int | None = None) -> list[T] | tuple[list[T], int]:
    if page is None:
        return list(session.scalars(query.limit(legacy_limit) if legacy_limit is not None else query))
    total = session.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar_one()
    items = list(session.scalars(query.limit(page_size).offset((page - 1) * page_size)))
    return items, total
