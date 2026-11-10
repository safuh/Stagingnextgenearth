"""Top-level API router."""

from fastapi import APIRouter

from .auth import router as auth_router
from .climate import router as climate_router
from .health import router as health_router
from .memberships import router as memberships_router
from .organizations import router as organizations_router
from .programmes import router as programmes_router
from .projects import router as projects_router
from .research import router as research_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(memberships_router)
api_router.include_router(programmes_router)
api_router.include_router(projects_router)
api_router.include_router(research_router)
api_router.include_router(climate_router)
