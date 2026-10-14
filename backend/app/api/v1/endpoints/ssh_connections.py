from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from ...dependencies import Database
from ....connection_models import ConnectionTest
from ....repositories.ssh_connections import list_tests
from ....schemas.ssh_connections import ConnectionTestInput, ConnectionTestResponse, TargetType

router = APIRouter(prefix="/ssh/connection-tests", tags=["SSH 连接"])


@router.post("", response_model=ConnectionTestResponse, status_code=202)
def start_test(data: ConnectionTestInput, request: Request, session: Database) -> ConnectionTest:
    return request.app.state.connection_tests.start(session, data)


@router.get("", response_model=list[ConnectionTestResponse])
def recent_tests(session: Database, target_type: TargetType, target_id: Annotated[int, Query(gt=0)]) -> list[ConnectionTest]:
    return list_tests(session, target_type, target_id)


@router.get("/{test_id}", response_model=ConnectionTestResponse)
def read_test(test_id: UUID, session: Database) -> ConnectionTest:
    record = session.get(ConnectionTest, str(test_id))
    if record is None:
        raise HTTPException(404, "连接测试不存在")
    return record


@router.post("/{test_id}/trust", status_code=410)
def trust_key(test_id: UUID) -> None:
    raise HTTPException(410, "旧测试确认接口已停用，请使用独立身份检查")
