"""Organisation membership invitation and acceptance workflows."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import Membership

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/memberships",
    tags=["memberships"],
)
InvitableRole = Literal[
    "programme_manager",
    "researcher",
    "youth_volunteer",
    "institutional_partner",
]


class MembershipInvite(BaseModel):
    """Invite an existing platform account into an organisation."""

    identifier: str = Field(min_length=3, max_length=320)
    role: InvitableRole


class MembershipRead(BaseModel):
    """Membership state visible to organisation administrators or its member."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str
    role: str
    status: str


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def invite_member(
    organization_id: str,
    body: MembershipInvite,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Invite an existing user; administrator privileges cannot be delegated here."""
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    user = await session.scalar(select(User).where(User.identifier == body.identifier))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    existing = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Membership already exists")
    invitation = Membership(
        organization_id=organization_id,
        user_id=user.id,
        role=body.role,
        status="invited",
    )
    session.add(invitation)
    try:
        await session.commit()
        await session.refresh(invitation)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Membership already exists") from exc
    return MembershipRead.model_validate(invitation)


@router.get("", response_model=list[MembershipRead])
async def list_memberships(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MembershipRead]:
    """Expose membership records only to organisation administrators."""
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    result = await session.scalars(
        select(Membership)
        .where(Membership.organization_id == organization_id)
        .order_by(Membership.created_at)
    )
    return [MembershipRead.model_validate(item) for item in result.all()]


@router.post("/{membership_id}/accept", response_model=MembershipRead)
async def accept_invitation(
    organization_id: str,
    membership_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Allow only the invited account to activate its own membership."""
    invitation = await session.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
            Membership.status == "invited",
        )
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    invitation.status = "active"
    await session.commit()
    await session.refresh(invitation)
    return MembershipRead.model_validate(invitation)
