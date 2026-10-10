from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...dependencies import Database, commit, find_group
from ....models import Host
from ....schemas.assets import HostInput, HostResponse, HostUpdate

router = APIRouter(tags=["资产管理"])


def find_host(session: Session, host_id: int) -> Host:
    host = session.get(Host, host_id)
    if host is None:
        raise HTTPException(404, "主机不存在")
    return host


@router.get("/hosts", response_model=list[HostResponse])
def list_hosts(session: Database, q: str = Query(default="", max_length=253), group_id: int | None = Query(default=None, gt=0)) -> list[Host]:
    statement = select(Host).order_by(Host.id.desc())
    if group_id is not None:
        statement = statement.where(Host.group_id == group_id)
    if q.strip():
        statement = statement.where(or_(Host.name.contains(q.strip(), autoescape=True), Host.address.contains(q.strip(), autoescape=True)))
    return list(session.scalars(statement))


@router.get("/hosts/{host_id}", response_model=HostResponse)
def get_host(host_id: int, session: Database) -> Host:
    return find_host(session, host_id)


def apply_host(data: HostInput, host: Host, request: Request, session: Session) -> None:
    find_group(session, data.group_id)
    values = data.model_dump(exclude={"password", "proxy_password", "version"})
    for prefix in ("", "proxy_"):
        active = not prefix or data.proxy_address is not None
        auth = getattr(data, f"{prefix}auth_type")
        encrypted_field = f"{prefix}password_encrypted"
        secret = getattr(data, f"{prefix}password")
        if active and auth == "password":
            if secret is not None:
                token = request.app.state.cipher.encrypt(secret.get_secret_value().encode()).decode()
            else:
                connection_fields = ("proxy_address", "proxy_username", "proxy_port") if prefix else ("address", "username", "port")
                if host.id is not None and any(getattr(host, field) != getattr(data, field) for field in connection_fields):
                    raise HTTPException(422, "连接信息已变更，请重新填写对应密码")
                token = getattr(host, encrypted_field)
            if token is None:
                raise HTTPException(422, "请填写跳板机密码" if prefix else "请填写 SSH 密码")
            setattr(host, encrypted_field, token)
            values[f"{prefix}key_path"] = None
        else:
            setattr(host, encrypted_field, None)
    for field, value in values.items():
        setattr(host, field, value)


@router.post("/hosts", response_model=HostResponse, status_code=201)
def create_host(data: HostInput, request: Request, session: Database) -> Host:
    host = Host()
    apply_host(data, host, request, session)
    session.add(host)
    commit(session)
    return host


@router.put("/hosts/{host_id}", response_model=HostResponse)
def update_host(host_id: int, data: HostUpdate, request: Request, session: Database) -> Host:
    host = find_host(session, host_id)
    if host.version != data.version:
        raise HTTPException(409, "主机已被修改，请重新打开编辑页面")
    apply_host(data, host, request, session)
    commit(session)
    return host


@router.delete("/hosts/{host_id}", status_code=204)
def delete_host(host_id: int, session: Database) -> Response:
    session.delete(find_host(session, host_id))
    commit(session)
    return Response(status_code=204)
