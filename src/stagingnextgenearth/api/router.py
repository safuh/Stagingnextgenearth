"""Top-level API router."""

from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
