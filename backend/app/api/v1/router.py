from fastapi import APIRouter

from .endpoints.health import router as health_router
from .endpoints.assets import router as assets_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(assets_router)
