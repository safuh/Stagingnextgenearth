"""Organisation-scoped project creation and discovery endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, Programme, Project

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(prefix="/organizations/{organization_id}/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    """Create a project within an organisation and optional programme."""

    title: str = Field(min_length=3, max_length=240)
    summary: str | None = Field(default=None, max_length=10000)
    programme_id: str | None = None
    country_code: str = Field(default="KE", min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    county: str | None = Field(default=None, max_length=120)


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


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    organization_id: str,
    body: ProjectCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRead:
    """Create a planned project; only administrators and programme managers may write."""
    if membership.role not in {"admin", "programme_manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient organisation permissions")
    if body.programme_id is not None:
        programme = await session.scalar(
            select(Programme.id).where(
                Programme.id == body.programme_id,
                Programme.organization_id == organization_id,
            )
        )
        if programme is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    project = Project(
        organization_id=organization_id,
        programme_id=body.programme_id,
        title=body.title.strip(),
        summary=body.summary,
        status="planned",
        country_code=body.country_code.upper(),
        county=body.county,
        created_by=principal.user_id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


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
