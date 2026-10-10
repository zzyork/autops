from fastapi import APIRouter

from .endpoints.health import router as health_router
from .endpoints.host_groups import router as host_groups_router
from .endpoints.hosts import router as hosts_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(host_groups_router)
api_router.include_router(hosts_router)
