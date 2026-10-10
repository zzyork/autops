from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .core.config import get_settings
from .schemas.health import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", tags=["基础接口"])
    async def root() -> dict[str, str]:
        return {"message": "Hello, FastAPI!"}

    @application.get("/health", response_model=HealthResponse, tags=["健康检查"])
    async def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
