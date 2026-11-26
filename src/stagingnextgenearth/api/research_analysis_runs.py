"""Tenant-scoped, read-only provenance history for research analysis runs."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, ResearchAnalysisRun, ResearchDataset

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)
from .research_collaborators import study_access_role

router = APIRouter(
    prefix="/organizations/{organization_id}/research-datasets",
    tags=["research-analysis"],
)

_HISTORY_ROLES = {
    "admin", "founder", "executive", "programme_manager", "researcher",
    "institutional_partner",
}
_PRIVILEGED_ROLES = {"admin", "founder", "executive"}


class ResearchAnalysisRunRead(BaseModel):
    """Immutable execution metadata; never includes dataset file contents."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    dataset_id: str
    study_id: str | None
    input_manifest_sha256: str
    input_file_versions: list[dict[str, object]]
    analysis_configuration: dict[str, object]
    software_name: str
    software_version: str
    code_revision: str | None
    parameters: dict[str, object]
    random_seed: int | None
    output_artifacts: list[dict[str, object]]
    created_by: str
    created_at: datetime


@router.get("/{dataset_id}/analysis-runs", response_model=list[ResearchAnalysisRunRead])
async def list_research_analysis_runs(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ResearchAnalysisRunRead]:
    """List immutable provenance records visible to this organisation member."""
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research dataset not found")

    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    has_registry_access = await membership_has_any_role(
        session, membership, _HISTORY_ROLES
    )
    if not has_registry_access and study_role is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Research analysis history access required"
        )
    is_privileged = await membership_has_any_role(
        session, membership, _PRIVILEGED_ROLES
    )
    if (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and not is_privileged
        and study_role is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research dataset not found")

    result = await session.scalars(
        select(ResearchAnalysisRun)
        .where(
            ResearchAnalysisRun.organization_id == organization_id,
            ResearchAnalysisRun.dataset_id == dataset_id,
        )
        .order_by(
            ResearchAnalysisRun.created_at.desc(),
            ResearchAnalysisRun.id.desc(),
        )
        .limit(limit)
    )
    return [ResearchAnalysisRunRead.model_validate(item) for item in result.all()]
