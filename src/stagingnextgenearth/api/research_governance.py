"""Versioned research protocol and independent ethics-review workflows."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchEthicsReviewEvent,
    ResearchProtocolReviewEvent,
    ResearchProtocolVersion,
    ResearchStudy,
    ResearchStudyCollaborator,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}",
    tags=["research-governance"],
)
_REVIEW_ROLES = {"admin", "programme_manager"}
_WRITE_ROLES = {"editor", "contributor"}


class ProtocolCreate(BaseModel):
    """Content for a new immutable protocol version."""

    title: str = Field(min_length=3, max_length=240)
    objectives: str = Field(min_length=20, max_length=12000)
    methodology: str = Field(min_length=30, max_length=20000)
    sampling_and_participants: str | None = Field(default=None, max_length=12000)
    data_management: str | None = Field(default=None, max_length=12000)
    risk_and_safeguarding: str | None = Field(default=None, max_length=12000)


class ProtocolRead(BaseModel):
    """Protocol version without internal account identifiers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    version_number: int
    title: str
    objectives: str
    methodology: str
    sampling_and_participants: str | None
    data_management: str | None
    risk_and_safeguarding: str | None
    status: str
    submitted_at: datetime | None
    created_at: datetime


class ProtocolReviewCreate(BaseModel):
    """Independent protocol review decision."""

    decision: Literal["approved", "revisions_required", "rejected"]
    note: str = Field(min_length=10, max_length=5000)


class ProtocolReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    protocol_version_id: str
    decision: str
    note: str | None
    reviewed_at: datetime


class EthicsReviewCreate(BaseModel):
    """Formal ethics committee outcome for an approved protocol version."""

    protocol_version_id: str
    decision: Literal["approved", "revisions_required", "rejected", "exempt"]
    reference: str | None = Field(default=None, max_length=160)
    note: str = Field(min_length=10, max_length=5000)


class EthicsReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    protocol_version_id: str | None
    decision: str
    reference: str | None
    note: str | None
    reviewed_at: datetime


async def _study(
    session: AsyncSession, organization_id: str, study_id: str
) -> ResearchStudy:
    study = await session.scalar(
        select(ResearchStudy).where(
            ResearchStudy.id == study_id,
            ResearchStudy.organization_id == organization_id,
        )
    )
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    return study


async def _study_role(
    session: AsyncSession,
    study: ResearchStudy,
    principal: Principal,
    membership: Membership,
) -> str | None:
    if membership.role == "admin" or study.lead_researcher_id == principal.user_id:
        return "editor"
    collaborator = await session.scalar(
        select(ResearchStudyCollaborator).where(
            ResearchStudyCollaborator.study_id == study.id,
            ResearchStudyCollaborator.organization_id == study.organization_id,
            ResearchStudyCollaborator.user_id == principal.user_id,
            ResearchStudyCollaborator.status == "active",
        )
    )
    return collaborator.role if collaborator is not None else None


async def _require_research_access(
    session: AsyncSession,
    study: ResearchStudy,
    principal: Principal,
    membership: Membership,
) -> str:
    role = await _study_role(session, study, principal, membership)
    if role is None and membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study access required")
    return role or "reviewer"


@router.post("/protocol-versions", response_model=ProtocolRead, status_code=201)
async def create_protocol_version(
    organization_id: str,
    study_id: str,
    body: ProtocolCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolRead:
    """Create a new protocol version; existing versions are never overwritten."""
    study = await _study(session, organization_id, study_id)
    role = await _require_research_access(session, study, principal, membership)
    if role not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Protocol authoring permission required")
    latest = await session.scalar(
        select(func.max(ResearchProtocolVersion.version_number)).where(
            ResearchProtocolVersion.study_id == study_id
        )
    )
    version = ResearchProtocolVersion(
        study_id=study_id,
        version_number=(latest or 0) + 1,
        title=body.title.strip(),
        objectives=body.objectives.strip(),
        methodology=body.methodology.strip(),
        sampling_and_participants=body.sampling_and_participants,
        data_management=body.data_management,
        risk_and_safeguarding=body.risk_and_safeguarding,
        status="draft",
        created_by=principal.user_id,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return ProtocolRead.model_validate(version)


@router.get("/protocol-versions", response_model=list[ProtocolRead])
async def list_protocol_versions(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProtocolRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    result = await session.scalars(
        select(ResearchProtocolVersion)
        .where(ResearchProtocolVersion.study_id == study_id)
        .order_by(ResearchProtocolVersion.version_number.desc())
    )
    return [ProtocolRead.model_validate(item) for item in result.all()]


@router.post("/protocol-versions/{protocol_id}/submit", response_model=ProtocolRead)
async def submit_protocol_version(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolRead:
    """Submit a draft or revision for independent review."""
    study = await _study(session, organization_id, study_id)
    role = await _require_research_access(session, study, principal, membership)
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    if role not in _WRITE_ROLES or (
        protocol.created_by != principal.user_id and role != "editor"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Protocol submission permission required")
    if protocol.status not in {"draft", "revisions_required"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Protocol version cannot be submitted")
    protocol.status = "submitted"
    protocol.submitted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(protocol)
    return ProtocolRead.model_validate(protocol)


@router.post(
    "/protocol-versions/{protocol_id}/reviews",
    response_model=ProtocolReviewRead,
    status_code=201,
)
async def review_protocol_version(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    body: ProtocolReviewCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolReviewRead:
    """Record an independent review; submitters cannot review their own version."""
    study = await _study(session, organization_id, study_id)
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    if membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Independent reviewer role required")
    if protocol.created_by == principal.user_id or study.lead_researcher_id == principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Authors and study leads cannot review")
    if protocol.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted protocols can be reviewed")
    event = ResearchProtocolReviewEvent(
        protocol_version_id=protocol.id,
        reviewer_user_id=principal.user_id,
        decision=body.decision,
        note=body.note.strip(),
    )
    protocol.status = body.decision
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return ProtocolReviewRead.model_validate(event)


@router.get(
    "/protocol-versions/{protocol_id}/reviews",
    response_model=list[ProtocolReviewRead],
)
async def list_protocol_reviews(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProtocolReviewRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    protocol = await session.scalar(
        select(ResearchProtocolVersion.id).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    result = await session.scalars(
        select(ResearchProtocolReviewEvent)
        .where(ResearchProtocolReviewEvent.protocol_version_id == protocol_id)
        .order_by(ResearchProtocolReviewEvent.reviewed_at)
    )
    return [ProtocolReviewRead.model_validate(item) for item in result.all()]


@router.post("/ethics-reviews", response_model=EthicsReviewRead, status_code=201)
async def record_ethics_review(
    organization_id: str,
    study_id: str,
    body: EthicsReviewCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EthicsReviewRead:
    """Record a formal ethics outcome, separate from protocol and dataset review."""
    study = await _study(session, organization_id, study_id)
    if membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ethics reviewer role required")
    if study.lead_researcher_id == principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study leads cannot review their own study")
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == body.protocol_version_id,
            ResearchProtocolVersion.study_id == study_id,
            ResearchProtocolVersion.status == "approved",
        )
    )
    if protocol is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ethics review must reference an approved protocol version for this study",
        )
    event = ResearchEthicsReviewEvent(
        study_id=study_id,
        protocol_version_id=protocol.id,
        reviewer_user_id=principal.user_id,
        decision=body.decision,
        reference=body.reference,
        note=body.note.strip(),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return EthicsReviewRead.model_validate(event)


@router.get("/ethics-reviews", response_model=list[EthicsReviewRead])
async def list_ethics_reviews(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EthicsReviewRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    result = await session.scalars(
        select(ResearchEthicsReviewEvent)
        .where(ResearchEthicsReviewEvent.study_id == study_id)
        .order_by(ResearchEthicsReviewEvent.reviewed_at)
    )
    return [EthicsReviewRead.model_validate(item) for item in result.all()]
