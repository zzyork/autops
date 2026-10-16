from fastapi import APIRouter, Request

from ....schemas.ssh_connections import ConnectionTestInput, ConnectionTestResponse

router = APIRouter(prefix="/ssh/connection-tests", tags=["SSH 连接"])


@router.post("", response_model=ConnectionTestResponse)
def start_test(data: ConnectionTestInput, request: Request) -> ConnectionTestResponse:
    return request.app.state.connection_tests.start(data)
