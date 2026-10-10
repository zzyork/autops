from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..models import HostGroup


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


Database = Annotated[Session, Depends(get_session)]


def commit(session: Session, stale_message: str = "主机已被修改，请重新打开编辑页面") -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "记录重复或关联数据已变更，请检查后重试") from None
    except StaleDataError:
        session.rollback()
        raise HTTPException(409, stale_message) from None


def find_group(session: Session, group_id: int) -> HostGroup:
    group = session.get(HostGroup, group_id)
    if group is None:
        raise HTTPException(404, "分组不存在")
    return group
