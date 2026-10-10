from fastapi import APIRouter

from ....schemas.health import HealthResponse

router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
