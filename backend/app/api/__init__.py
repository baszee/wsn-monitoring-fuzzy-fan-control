from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.endpoints import router as monitoring_router
from app.api.public import router as public_router

api_router = APIRouter()
api_router.include_router(monitoring_router)
api_router.include_router(auth_router)
api_router.include_router(public_router)

__all__ = ["api_router"]
