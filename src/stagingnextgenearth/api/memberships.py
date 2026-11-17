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
    MembershipRole,
    Organization,
    OrganizationAuditEvent,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_membership_roles,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/memberships",
    tags=["memberships"],
)
InvitableRole = Literal[
    "programme_manager",
    "founder",
    "executive",
    "employee",
    "researcher",
    "youth_volunteer",
    "institutional_partner",
    "learner",
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
    identifier: str | None = None
    role: str
    status: str
    roles: list[str] = Field(default_factory=list)


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def invite_member(
    organization_id: str,
    body: MembershipInvite,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Invite an existing user; administrator privileges cannot be delegated here."""
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    if body.role in {"founder", "executive"}:
        owner_id = await session.scalar(
            select(Organization.owner_user_id).where(Organization.id == organization_id)
        )
        if owner_id != membership.user_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only the organisation owner can invite founders or executives",
            )
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
    await session.flush()
    session.add(MembershipRole(membership_id=invitation.id, role=body.role))
    try:
        await session.commit()
        await session.refresh(invitation)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Membership already exists") from exc
    roles = sorted(await get_membership_roles(session, invitation))
    return MembershipRead.model_validate(invitation).model_copy(
        update={"identifier": user.identifier, "roles": roles}
    )


@router.get("/me", response_model=MembershipRead)
async def get_my_membership(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Return the caller's own active tenant membership and role."""
    if membership.organization_id != organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    identifier = await session.scalar(
        select(User.identifier).where(User.id == membership.user_id)
    )
    roles = sorted(await get_membership_roles(session, membership))
    return MembershipRead.model_validate(membership).model_copy(
        update={"identifier": identifier, "roles": roles}
    )


@router.get("/directory")
async def list_staff_directory(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return minimal active-member identities to authorised programme staff."""
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive", "programme_manager"}):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme staff access required",
        )
    rows = await session.scalars(
        select(Membership)
        .where(
            Membership.organization_id == organization_id,
            Membership.status == "active",
        )
        .order_by(Membership.role, Membership.user_id)
        .limit(1000)
    )
    directory: list[dict[str, object]] = []
    for item in rows.all():
        directory.append(
            {
                "user_id": item.user_id,
                "role": item.role,
                "roles": sorted(await get_membership_roles(session, item)),
            }
        )
    return directory


@router.get("", response_model=list[MembershipRead])
async def list_memberships(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MembershipRead]:
    """Expose membership records only to organisation administrators."""
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    result = await session.execute(
        select(Membership, User.identifier)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
        .order_by(Membership.created_at)
    )
    reads: list[MembershipRead] = []
    for item, identifier in result.all():
        roles = sorted(await get_membership_roles(session, item))
        reads.append(
            MembershipRead.model_validate(item).model_copy(
                update={"identifier": identifier, "roles": roles}
            )
        )
    return reads


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
    identifier = await session.scalar(
        select(User.identifier).where(User.id == invitation.user_id)
    )
    roles = sorted(await get_membership_roles(session, invitation))
    return MembershipRead.model_validate(invitation).model_copy(
        update={"identifier": identifier, "roles": roles}
    )


class MembershipRoleUpdate(BaseModel):
    """Validated role change; administrator grants are owner-controlled."""

    role: Literal[
        "admin",
        "programme_manager",
        "founder",
        "executive",
        "employee",
        "researcher",
        "youth_volunteer",
        "institutional_partner",
        "learner",
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
    if (
        actor is None
        or actor.status != "active"
        or not await membership_has_any_role(
            session, actor, {"admin", "founder", "executive"}
        )
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Active administrator role required",
        )
    return actor


async def _active_admin_count(session: AsyncSession, organization_id: str) -> int:
    """Count active administrators before a potentially demoting operation."""
    elevated_roles = {"admin", "founder", "executive"}
    count = await session.scalar(
        select(func.count(func.distinct(Membership.id)))
        .outerjoin(
            MembershipRole,
            MembershipRole.membership_id == Membership.id,
        )
        .where(
            Membership.organization_id == organization_id,
            Membership.status == "active",
            (Membership.role.in_(elevated_roles))
            | (MembershipRole.role.in_(elevated_roles)),
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
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
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
    if body.role in {"admin", "founder", "executive"} and membership.user_id != owner_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the organisation owner can grant administrator access",
        )
    target_roles = await get_membership_roles(session, target)
    if (
        target_roles & {"admin", "founder", "executive"}
        and body.role not in {"admin", "founder", "executive"}
        and membership.user_id != owner_id
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the organisation owner can revoke elevated administrator access",
        )
    if (
        target.status == "active"
        and target_roles & {"admin", "founder", "executive"}
        and body.role not in {"admin", "founder", "executive"}
    ):
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
    await session.execute(
        MembershipRole.__table__.delete().where(
            MembershipRole.membership_id == target.id,
            MembershipRole.role == previous_role,
        )
    )
    session.add(MembershipRole(membership_id=target.id, role=body.role))
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
    roles = sorted(await get_membership_roles(session, target))
    return MembershipRead.model_validate(target).model_copy(update={"roles": roles})


@router.patch("/{membership_id}/status", response_model=MembershipRead)
async def update_member_status(
    organization_id: str,
    membership_id: str,
    body: MembershipStatusUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MembershipRead:
    """Suspend or reactivate a member while preserving an active organisation owner."""
    if not await membership_has_any_role(
        session, membership, {"admin", "founder", "executive"}
    ):
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
    target_roles = await get_membership_roles(session, target)
    if (
        target_roles & {"admin", "founder", "executive"}
        and body.status == "suspended"
        and membership.user_id != owner_id
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the organisation owner can suspend an elevated administrator",
        )
    if (
        target.status == "active"
        and target_roles & {"admin", "founder", "executive"}
        and body.status == "suspended"
    ):
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
