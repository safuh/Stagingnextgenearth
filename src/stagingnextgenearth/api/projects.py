"""Organisation-scoped project discovery endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, Project

from .dependencies import get_session, require_membership

router = APIRouter(prefix="/organizations/{organization_id}/projects", tags=["projects"])


class ProjectRead(BaseModel):
    """Project response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str | None
    title: str
    summary: str | None
    status: str
    country_code: str
    county: str | None


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProjectRead]:
    """List projects inside an organisation the caller actively belongs to."""
    result = await session.scalars(
        select(Project)
        .where(Project.organization_id == organization_id)
        .order_by(Project.created_at.desc())
    )
    return [ProjectRead.model_validate(item) for item in result.all()]
