from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...dependencies import Database, commit, find_group
from ....models import Host, HostGroup
from ....repositories import assets as repository
from ....schemas.assets import GroupInput, GroupResponse
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize

router = APIRouter(tags=["资产管理"])


def group_response(session: Session, group: HostGroup) -> GroupResponse:
    count = session.scalar(select(func.count()).select_from(Host).where(Host.group_id == group.id))
    return GroupResponse(id=group.id, name=group.name, remark=group.remark, host_count=count)


@router.get("/host-groups", response_model=list[GroupResponse] | PageResponse[GroupResponse])
def list_groups(session: Database, page: PageNumber = None,
                 page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[GroupResponse] | PageResponse[GroupResponse]:
    result = repository.groups(session, page, page_size)
    if page is None:
        return [group_response(session, group) for group in result]
    items, total = result
    return PageResponse[GroupResponse](items=[group_response(session, group) for group in items], total=total)


@router.post("/host-groups", response_model=GroupResponse, status_code=201)
def create_group(data: GroupInput, session: Database) -> GroupResponse:
    group = HostGroup(**data.model_dump())
    session.add(group)
    commit(session)
    return group_response(session, group)


@router.put("/host-groups/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, data: GroupInput, session: Database) -> GroupResponse:
    group = find_group(session, group_id)
    group.name, group.remark = data.name, data.remark
    commit(session)
    return group_response(session, group)


@router.delete("/host-groups/{group_id}", status_code=204)
def delete_group(group_id: int, session: Database) -> Response:
    group = find_group(session, group_id)
    if session.scalar(select(Host.id).where(Host.group_id == group_id).limit(1)) is not None:
        raise HTTPException(409, "分组中仍有主机，请先移动或删除主机")
    session.delete(group)
    commit(session)
    return Response(status_code=204)
