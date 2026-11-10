"""Study-level collaborator invitations and access management."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import (
    Membership,
    ResearchStudy,
    ResearchStudyCollaborator,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}/collaborators",
    tags=["research"],
)


class CollaboratorInvite(BaseModel):
    """Invite an existing active organisation member to a study."""

    identifier: str = Field(min_length=3, max_length=320)
    role: Literal["editor", "contributor", "viewer"]


class CollaboratorRead(BaseModel):
    """Study collaborator invitation and access state."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    organization_id: str
    user_id: str
    role: str
    status: str
    invited_by: str
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


async def _get_study(
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


def _can_manage(study: ResearchStudy, principal: Principal, membership: Membership) -> bool:
    return membership.role == "admin" or study.lead_researcher_id == principal.user_id


@router.post("", response_model=CollaboratorRead, status_code=status.HTTP_201_CREATED)
async def invite_study_collaborator(
    organization_id: str,
    study_id: str,
    body: CollaboratorInvite,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollaboratorRead:
    """Allow the study lead or organisation admin to invite an active member."""
    study = await _get_study(session, organization_id, study_id)
    if not _can_manage(study, principal, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study lead or administrator required")

    user = await session.scalar(select(User).where(User.identifier == body.identifier))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    target_membership = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
            Membership.status == "active",
        )
    )
    if target_membership is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Collaborator must be an active member of this organisation",
        )
    if user.id == study.lead_researcher_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Study lead already has study access")

    collaborator = ResearchStudyCollaborator(
        study_id=study.id,
        organization_id=organization_id,
        user_id=user.id,
        role=body.role,
        status="invited",
        invited_by=principal.user_id,
    )
    session.add(collaborator)
    try:
        await session.commit()
        await session.refresh(collaborator)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A collaborator record already exists for this study and account",
        ) from exc
    return CollaboratorRead.model_validate(collaborator)


@router.get("", response_model=list[CollaboratorRead])
async def list_study_collaborators(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CollaboratorRead]:
    """List collaborators for the lead, administrators, or active collaborators."""
    study = await _get_study(session, organization_id, study_id)
    if not _can_manage(study, principal, membership):
        active_collaboration = await session.scalar(
            select(ResearchStudyCollaborator.id).where(
                ResearchStudyCollaborator.study_id == study_id,
                ResearchStudyCollaborator.user_id == principal.user_id,
                ResearchStudyCollaborator.status == "active",
            )
        )
        if active_collaboration is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Study collaborator access required")
    result = await session.scalars(
        select(ResearchStudyCollaborator)
        .where(ResearchStudyCollaborator.study_id == study_id)
        .order_by(ResearchStudyCollaborator.created_at)
    )
    return [CollaboratorRead.model_validate(item) for item in result.all()]


@router.post("/{collaborator_id}/accept", response_model=CollaboratorRead)
async def accept_study_invitation(
    organization_id: str,
    study_id: str,
    collaborator_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollaboratorRead:
    """Only the invited user may accept; an active organisation membership is required."""
    invitation = await session.scalar(
        select(ResearchStudyCollaborator).where(
            ResearchStudyCollaborator.id == collaborator_id,
            ResearchStudyCollaborator.study_id == study_id,
            ResearchStudyCollaborator.organization_id == organization_id,
            ResearchStudyCollaborator.user_id == principal.user_id,
            ResearchStudyCollaborator.status == "invited",
        )
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study invitation not found")
    invitation.status = "active"
    invitation.accepted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(invitation)
    return CollaboratorRead.model_validate(invitation)


@router.delete("/{collaborator_id}", response_model=CollaboratorRead)
async def revoke_study_collaborator(
    organization_id: str,
    study_id: str,
    collaborator_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CollaboratorRead:
    """Revoke an invitation or active collaboration without deleting its history."""
    study = await _get_study(session, organization_id, study_id)
    if not _can_manage(study, principal, membership):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study lead or administrator required")
    collaborator = await session.scalar(
        select(ResearchStudyCollaborator).where(
            ResearchStudyCollaborator.id == collaborator_id,
            ResearchStudyCollaborator.study_id == study_id,
            ResearchStudyCollaborator.organization_id == organization_id,
            ResearchStudyCollaborator.status.in_({"invited", "active"}),
        )
    )
    if collaborator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active collaborator not found")
    collaborator.status = "revoked"
    collaborator.revoked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(collaborator)
    return CollaboratorRead.model_validate(collaborator)
