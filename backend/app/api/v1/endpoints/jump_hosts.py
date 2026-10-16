from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ...dependencies import Database, commit
from ....models import Host, JumpHost
from ....repositories import assets as repository
from ....schemas.jump_hosts import JumpHostInput, JumpHostResponse, JumpHostUpdate
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize
from .credentials import apply_connection

router = APIRouter(tags=["资产管理"])
STALE_MESSAGE = "跳板机已被修改，请重新打开编辑页面"


def find_jump_host(session: Session, jump_host_id: int) -> JumpHost:
    jump_host = session.get(JumpHost, jump_host_id)
    if jump_host is None:
        raise HTTPException(404, "跳板机不存在")
    return jump_host


def jump_host_response(session: Session, jump_host: JumpHost) -> JumpHostResponse:
    count = session.scalar(select(func.count()).select_from(Host).where(Host.jump_host_id == jump_host.id))
    return JumpHostResponse.model_validate({
        **{field: getattr(jump_host, field) for field in JumpHostResponse.model_fields if field != "host_count"},
        "host_count": count,
    })


@router.get("/jump-hosts", response_model=list[JumpHostResponse] | PageResponse[JumpHostResponse])
def list_jump_hosts(session: Database, q: str = Query(default="", max_length=253),
                    page: PageNumber = None,
                     page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[JumpHostResponse] | PageResponse[JumpHostResponse]:
    result = repository.jump_hosts(session, q, page, page_size)
    if page is None:
        return [jump_host_response(session, item) for item in result]
    items, total = result
    return PageResponse[JumpHostResponse](items=[jump_host_response(session, item) for item in items], total=total)


@router.get("/jump-hosts/{jump_host_id}", response_model=JumpHostResponse)
def get_jump_host(jump_host_id: int, session: Database) -> JumpHostResponse:
    return jump_host_response(session, find_jump_host(session, jump_host_id))


@router.post("/jump-hosts", response_model=JumpHostResponse, status_code=201)
def create_jump_host(data: JumpHostInput, request: Request, session: Database) -> JumpHostResponse:
    jump_host = JumpHost()
    apply_connection(data, jump_host, request, "请填写跳板机密码", session)
    session.add(jump_host)
    commit(session, STALE_MESSAGE)
    return jump_host_response(session, jump_host)


@router.put("/jump-hosts/{jump_host_id}", response_model=JumpHostResponse)
def update_jump_host(jump_host_id: int, data: JumpHostUpdate, request: Request, session: Database) -> JumpHostResponse:
    jump_host = find_jump_host(session, jump_host_id)
    if jump_host.version != data.version:
        raise HTTPException(409, STALE_MESSAGE)
    connection_changed = data.password is not None or any(
        getattr(jump_host, field) != getattr(data, field)
        for field in ("address", "port", "username", "auth_type", "ssh_key_id")
    )
    apply_connection(data, jump_host, request, "请填写跳板机密码", session)
    affected = update(Host).where(Host.jump_host_id == jump_host_id)
    if not connection_changed:
        affected = affected.where(Host.connection_status == "running")
    session.execute(affected.values(connection_status="untested" if connection_changed else "interrupted",
             updated_at=Host.updated_at).execution_options(synchronize_session=False))
    commit(session, STALE_MESSAGE)
    return jump_host_response(session, jump_host)


@router.delete("/jump-hosts/{jump_host_id}", status_code=204)
def delete_jump_host(jump_host_id: int, session: Database) -> Response:
    jump_host = find_jump_host(session, jump_host_id)
    if session.scalar(select(Host.id).where(Host.jump_host_id == jump_host_id).limit(1)) is not None:
        raise HTTPException(409, "跳板机仍被主机引用，请先解除关联")
    session.delete(jump_host)
    commit(session, STALE_MESSAGE)
    return Response(status_code=204)
