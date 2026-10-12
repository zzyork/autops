from fastapi import APIRouter

from .endpoints.health import router as health_router
from .endpoints.host_groups import router as host_groups_router
from .endpoints.hosts import router as hosts_router
from .endpoints.jump_hosts import router as jump_hosts_router
from .endpoints.ssh_keys import router as ssh_keys_router
from .endpoints.ssh_connections import router as ssh_connections_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(host_groups_router)
api_router.include_router(hosts_router)
api_router.include_router(jump_hosts_router)
api_router.include_router(ssh_keys_router)
api_router.include_router(ssh_connections_router)
