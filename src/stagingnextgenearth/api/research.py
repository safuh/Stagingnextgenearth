"""Research study workspace endpoints with strict organisation scoping."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    OrganizationAuditEvent,
    Project,
    ResearchEthicsReviewEvent,
    ResearchProtocolVersion,
    ResearchPublication,
    ResearchStudy,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies",
    tags=["research"],
)
_RESEARCH_ROLES = {
    "admin",
    "founder",
    "executive",
    "programme_manager",
    "researcher",
    "institutional_partner",
}


class ResearchStudyCreate(BaseModel):
    """Create a research study in an organisation."""

    title: str = Field(min_length=3, max_length=240)
    abstract: str | None = Field(default=None, max_length=20000)
    study_type: str | None = Field(default=None, max_length=80)
    project_id: str | None = None
    ethics_reference: str | None = Field(default=None, max_length=160)


class ResearchStudyStatusUpdate(BaseModel):
    """Target state for a governed research-study lifecycle transition."""

    status: Literal["protocol", "active", "completed", "published", "archived"]


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
    if not await membership_has_any_role(session, membership, _RESEARCH_ROLES):
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
    if not await membership_has_any_role(session, membership, _RESEARCH_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research workspace access required")
    result = await session.scalars(
        select(ResearchStudy)
        .where(ResearchStudy.organization_id == organization_id)
        .order_by(ResearchStudy.created_at.desc())
    )
    return [ResearchStudyRead.model_validate(item) for item in result.all()]


@router.patch("/{study_id}/status", response_model=ResearchStudyRead)
async def update_research_study_status(
    organization_id: str,
    study_id: str,
    body: ResearchStudyStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchStudyRead:
    """Advance a study through protocol, ethics, delivery and publication gates."""
    if not await membership_has_any_role(
        session, membership, {"admin", "founder", "executive", "programme_manager"}
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Research lifecycle management permission required"
        )
    study = await session.scalar(
        select(ResearchStudy)
        .where(ResearchStudy.id == study_id, ResearchStudy.organization_id == organization_id)
        .with_for_update()
    )
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")

    transitions = {
        "concept": "protocol",
        "protocol": "active",
        "active": "completed",
        "completed": "published",
        "published": "archived",
    }
    target = body.status
    if transitions.get(study.status) != target:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Study cannot transition from {study.status} to {target}",
        )

    activation_ethics_decision: ResearchEthicsReviewEvent | None = None
    activation_protocol: ResearchProtocolVersion | None = None
    if target in {"protocol", "active"}:
        latest_protocol = await session.scalar(
            select(ResearchProtocolVersion)
            .where(ResearchProtocolVersion.study_id == study_id)
            .order_by(
                ResearchProtocolVersion.version_number.desc(), ResearchProtocolVersion.id.desc()
            )
            .limit(1)
        )
        activation_protocol = latest_protocol
        if latest_protocol is None or latest_protocol.status != "approved":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The latest protocol version must be approved before this transition",
            )
        if target == "active":
            ethics_decision = await session.scalar(
                select(ResearchEthicsReviewEvent)
                .where(
                    ResearchEthicsReviewEvent.study_id == study_id,
                    ResearchEthicsReviewEvent.protocol_version_id == latest_protocol.id,
                )
                .order_by(
                    ResearchEthicsReviewEvent.reviewed_at.desc(),
                    ResearchEthicsReviewEvent.id.desc(),
                )
                .limit(1)
            )
            activation_ethics_decision = ethics_decision
            if ethics_decision is None or ethics_decision.decision not in {"approved", "exempt"}:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "A matching ethics approval or exemption is required before activation",
                )
    if target == "published":
        publication_id = await session.scalar(
            select(ResearchPublication.id).where(ResearchPublication.study_id == study_id).limit(1)
        )
        if publication_id is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "At least one linked publication is required before publication status",
            )

    previous_status = study.status
    study.status = target
    changes: dict[str, str | None] = {
        "study_id": study_id,
        "from_status": previous_status,
        "to_status": target,
    }
    if target == "active":
        # Record the exact committee evidence that authorised fieldwork resumption.
        assert activation_protocol is not None
        assert activation_ethics_decision is not None
        changes.update(
            {
                "protocol_version_id": activation_protocol.id,
                "ethics_review_event_id": activation_ethics_decision.id,
                "ethics_reviewer_user_id": activation_ethics_decision.reviewer_user_id,
                "ethics_decision": activation_ethics_decision.decision,
                "ethics_reference": activation_ethics_decision.reference,
            }
        )
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            action="research.study.status_changed",
            changes=changes,
        )
    )
    await session.commit()
    await session.refresh(study)
    return ResearchStudyRead.model_validate(study)
