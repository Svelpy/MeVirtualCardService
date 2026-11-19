from fastapi import APIRouter

from app.core.system_router import router as system_router


no_system_router = APIRouter(prefix="/api/v1")



api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(no_system_router)
