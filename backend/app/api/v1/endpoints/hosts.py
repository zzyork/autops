from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...dependencies import Database, commit, find_group
from ....models import Host, JumpHost
from ....repositories import assets as repository
from ....repositories.ssh_connections import set_host_status
from ....schemas.assets import HostInput, HostResponse, HostUpdate
from ....schemas.host_basic_info import HostBasicInfoCollect, HostBasicInfoResponse, HostBasicInfoUpdate
from ....schemas.pagination import DEFAULT_PAGE_SIZE, PageNumber, PageResponse, PageSize
from .credentials import apply_connection

router = APIRouter(tags=["资产管理"])


def find_host(session: Session, host_id: int) -> Host:
    host = session.get(Host, host_id)
    if host is None:
        raise HTTPException(404, "主机不存在")
    return host


@router.get("/hosts", response_model=list[HostResponse] | PageResponse[HostResponse])
def list_hosts(session: Database, q: str = Query(default="", max_length=253),
               group_id: int | None = Query(default=None, gt=0), page: PageNumber = None,
               page_size: PageSize = DEFAULT_PAGE_SIZE) -> list[Host] | PageResponse[HostResponse]:
    result = repository.hosts(session, q, group_id, page, page_size)
    if page is None:
        return result
    items, total = result
    return PageResponse[HostResponse](items=[HostResponse.model_validate(item) for item in items], total=total)


@router.get("/hosts/{host_id}", response_model=HostResponse)
def get_host(host_id: int, session: Database) -> Host:
    return find_host(session, host_id)


def apply_host(data: HostInput, host: Host, request: Request, session: Session) -> None:
    find_group(session, data.group_id)
    if data.jump_host_id is not None and session.get(JumpHost, data.jump_host_id) is None:
        raise HTTPException(404, "跳板机不存在")
    if host.id is not None and "lan_ip" not in data.model_fields_set:
        data = data.model_copy(update={"lan_ip": host.lan_ip})
    apply_connection(data, host, request, "请填写 SSH 密码", session)


@router.post("/hosts", response_model=HostResponse, status_code=201)
def create_host(data: HostInput, request: Request, session: Database) -> Host:
    host = Host()
    apply_host(data, host, request, session)
    session.add(host)
    commit(session)
    return host


@router.put("/hosts/{host_id}", response_model=HostResponse)
def update_host(host_id: int, data: HostUpdate, request: Request, session: Database) -> Host:
    session.execute(text("BEGIN IMMEDIATE"))
    host = find_host(session, host_id)
    if host.version != data.version:
        raise HTTPException(409, "主机已被修改，请重新打开编辑页面")
    connection_changed = data.password is not None or any(
        getattr(host, field) != getattr(data, field)
        for field in ("address", "vip", "port", "username", "auth_type", "ssh_key_id", "jump_host_id")
    )
    apply_host(data, host, request, session)
    # The loaded host may predate a status-only write; use the database value before flushing asset edits.
    with session.no_autoflush:
        set_host_status(session, host.id, host.created_at, host.version,
                        "untested" if connection_changed else "interrupted",
                        expected_status=None if connection_changed else "running")
    commit(session)
    return host


@router.delete("/hosts/{host_id}", status_code=204)
def delete_host(host_id: int, session: Database) -> Response:
    session.delete(find_host(session, host_id))
    commit(session)
    return Response(status_code=204)


@router.post("/hosts/{host_id}/basic-info/collect", response_model=HostBasicInfoResponse)
def collect_basic_info(host_id: int, data: HostBasicInfoCollect, request: Request) -> HostBasicInfoResponse:
    return request.app.state.host_basic_info.collect(host_id, data.version)


@router.patch("/hosts/{host_id}/basic-info", response_model=HostResponse)
def update_basic_info(host_id: int, data: HostBasicInfoUpdate, session: Database) -> Host:
    session.execute(text("BEGIN IMMEDIATE"))
    host = find_host(session, host_id)
    if host.version != data.version:
        raise HTTPException(409, "主机已被修改，请重新获取基础信息")
    host.name = data.name
    host.lan_ip = data.lan_ip
    with session.no_autoflush:
        set_host_status(session, host.id, host.created_at, host.version, "interrupted", expected_status="running")
    commit(session)
    return host
