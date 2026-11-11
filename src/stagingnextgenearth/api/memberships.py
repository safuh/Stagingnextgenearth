"""Organisation membership invitation and acceptance workflows."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import (
    Membership,
    Organization,
    OrganizationAuditEvent,
)

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


@router.get("/me", response_model=MembershipRead)
async def get_my_membership(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
) -> MembershipRead:
    """Return the caller's own active tenant membership and role."""
    if membership.organization_id != organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    return MembershipRead.model_validate(membership)


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


class MembershipRoleUpdate(BaseModel):
    """Validated role change; administrator grants are owner-controlled."""

    role: Literal[
        "admin",
        "programme_manager",
        "researcher",
        "youth_volunteer",
        "institutional_partner",
    ]


class MembershipStatusUpdate(BaseModel):
    """Activate or suspend an existing organisation membership."""

    status: Literal["active", "suspended"]


async def _organization_owner(session: AsyncSession, organization_id: str) -> str:
    """Return the tenant owner, failing closed if the tenant is missing."""
    owner_id = await session.scalar(
        select(Organization.owner_user_id)
        .where(Organization.id == organization_id)
        .with_for_update()
    )
    if owner_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return owner_id


async def _current_admin(
    session: AsyncSession,
    membership_id: str,
) -> Membership:
    """Reload and lock the actor membership after locking the tenant row."""
    actor = await session.scalar(
        select(Membership)
        .where(Membership.id == membership_id)
        .with_for_update()
    )
    if actor is None or actor.status != "active" or actor.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Active administrator role required",
        )
    return actor


async def _active_admin_count(session: AsyncSession, organization_id: str) -> int:
    """Count active administrators before a potentially demoting operation."""
    count = await session.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == organization_id,
            Membership.role == "admin",
            Membership.status == "active",
        )
    )
    return int(count or 0)


@router.patch("/{membership_id}/role", response_model=MembershipRead)
async def update_member_role(
    organization_id: str,
    membership_id: str,
    body: MembershipRoleUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Change a member role without permitting privilege escalation by non-admins."""
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    owner_id = await _organization_owner(session, organization_id)
    actor = await _current_admin(session, membership.id)
    target = await session.scalar(
        select(Membership)
        .where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
        .with_for_update()
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    if target.user_id == owner_id and body.role != "admin":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Transfer organisation ownership before changing the owner's role",
        )
    if body.role == "admin" and membership.user_id != owner_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the organisation owner can grant administrator access",
        )
    if target.status == "active" and target.role == "admin" and body.role != "admin":
        if (
            target.user_id == membership.user_id
            or await _active_admin_count(session, organization_id) <= 1
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The last active administrator cannot be demoted",
            )
    previous_role = target.role
    target.role = body.role
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=actor.user_id,
            subject_user_id=target.user_id,
            action="membership.role_changed",
            changes={"role": {"before": previous_role, "after": body.role}},
        )
    )
    await session.commit()
    await session.refresh(target)
    return MembershipRead.model_validate(target)


@router.patch("/{membership_id}/status", response_model=MembershipRead)
async def update_member_status(
    organization_id: str,
    membership_id: str,
    body: MembershipStatusUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Suspend or reactivate a member while preserving an active organisation owner."""
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    owner_id = await _organization_owner(session, organization_id)
    actor = await _current_admin(session, membership.id)
    target = await session.scalar(
        select(Membership)
        .where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
        .with_for_update()
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    if target.user_id == owner_id and body.status == "suspended":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Transfer organisation ownership before suspending the owner",
        )
    if target.status == "active" and target.role == "admin" and body.status == "suspended":
        if (
            target.user_id == membership.user_id
            or await _active_admin_count(session, organization_id) <= 1
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The last active administrator cannot be suspended",
            )
    previous_status = target.status
    target.status = body.status
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=actor.user_id,
            subject_user_id=target.user_id,
            action="membership.status_changed",
            changes={"status": {"before": previous_status, "after": body.status}},
        )
    )
    await session.commit()
    await session.refresh(target)
    return MembershipRead.model_validate(target)
