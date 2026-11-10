"""Top-level API router."""

from fastapi import APIRouter

from .auth import router as auth_router
from .climate import router as climate_router
from .health import router as health_router
from .learning import router as learning_router
from .memberships import router as memberships_router
from .organizations import router as organizations_router
from .programmes import router as programmes_router
from .programme_deliverables import router as programme_deliverables_router
from .projects import router as projects_router
from .research import router as research_router
from .research_collaborators import router as research_collaborators_router
from .research_dataset_files import router as research_dataset_files_router
from .research_datasets import router as research_datasets_router
from .research_exports import router as research_exports_router
from .research_governance import router as research_governance_router
from .research_planning import router as research_planning_router
from .research_publications import router as research_publications_router
from .researcher_profiles import directory_router as researcher_profile_directory_router
from .researcher_profiles import router as researcher_profiles_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(memberships_router)
api_router.include_router(learning_router)
api_router.include_router(programmes_router)
api_router.include_router(programme_deliverables_router)
api_router.include_router(projects_router)
api_router.include_router(research_router)
api_router.include_router(researcher_profiles_router)
api_router.include_router(researcher_profile_directory_router)
api_router.include_router(research_collaborators_router)
api_router.include_router(research_governance_router)
api_router.include_router(research_planning_router)
api_router.include_router(research_publications_router)
api_router.include_router(research_datasets_router)
api_router.include_router(research_dataset_files_router)
api_router.include_router(research_exports_router)
api_router.include_router(climate_router)
