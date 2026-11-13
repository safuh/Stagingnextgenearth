"""Research study workspace endpoints with strict organisation scoping."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, Project, ResearchStudy

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies",
    tags=["research"],
)
_RESEARCH_ROLES = {"admin", "programme_manager", "researcher", "institutional_partner"}


class ResearchStudyCreate(BaseModel):
    """Create a research study in an organisation."""

    title: str = Field(min_length=3, max_length=240)
    abstract: str | None = Field(default=None, max_length=20000)
    study_type: str | None = Field(default=None, max_length=80)
    project_id: str | None = None
    ethics_reference: str | None = Field(default=None, max_length=160)


class ResearchStudyRead(BaseModel):
    """Research study metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    project_id: str | None
    title: str
    abstract: str | None
    study_type: str | None
    status: str
    lead_researcher_id: str
    ethics_reference: str | None


@router.post("", response_model=ResearchStudyRead, status_code=status.HTTP_201_CREATED)
async def create_research_study(
    organization_id: str,
    body: ResearchStudyCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchStudyRead:
    """Create a concept study and bind its lead researcher to the caller."""
    if membership.role not in _RESEARCH_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research workspace access required")
    if body.project_id is not None:
        project = await session.scalar(
            select(Project.id).where(
                Project.id == body.project_id,
                Project.organization_id == organization_id,
            )
        )
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    study = ResearchStudy(
        organization_id=organization_id,
        project_id=body.project_id,
        title=body.title.strip(),
        abstract=body.abstract,
        study_type=body.study_type,
        status="concept",
        lead_researcher_id=principal.user_id,
        ethics_reference=body.ethics_reference,
    )
    session.add(study)
    await session.commit()
    await session.refresh(study)
    return ResearchStudyRead.model_validate(study)


@router.get("", response_model=list[ResearchStudyRead])
async def list_research_studies(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ResearchStudyRead]:
    """List studies only for members with an appropriate research role."""
    if membership.role not in _RESEARCH_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research workspace access required")
    result = await session.scalars(
        select(ResearchStudy)
        .where(ResearchStudy.organization_id == organization_id)
        .order_by(ResearchStudy.created_at.desc())
    )
    return [ResearchStudyRead.model_validate(item) for item in result.all()]
