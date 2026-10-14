from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ...dependencies import Database
from ....schemas.ssh_identities import (IdentityCheckInput, IdentityCheckResponse,
                                        IdentityTrustInput, IdentityTrustResponse)
from ....services.ssh_identities import check_identity, trust_identity

router = APIRouter(prefix="/ssh/identities", tags=["SSH 身份"])


@router.post("/check", response_model=IdentityCheckResponse)
def check(data: IdentityCheckInput, request: Request, session: Database) -> IdentityCheckResponse:
    return check_identity(session, request.app.state.cipher, data)


@router.post("/{challenge_id}/trust", response_model=IdentityTrustResponse)
def trust(challenge_id: UUID, data: IdentityTrustInput, request: Request, session: Database) -> IdentityTrustResponse:
    if data.confirmed is not True:
        raise HTTPException(422, "请确认服务器身份")
    trust_identity(session, request.app.state.cipher, str(challenge_id))
    return IdentityTrustResponse(trusted=True)
