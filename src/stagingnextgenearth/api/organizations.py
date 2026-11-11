"""Organisation creation and membership-scoped discovery endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Organization,
    OrganizationAuditEvent,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership


router = APIRouter(prefix="/organizations", tags=["organizations"])

class OrganizationCreate(BaseModel):
    """Validated organisation creation payload."""

    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    country_code: str = Field(default="KE", min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")


class OrganizationRead(BaseModel):
    """Public organisation representation for an authenticated member."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None
    country_code: str


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationRead:
    """Create a tenant and atomically grant its creator the administrator role."""
    organization = Organization(
        name=body.name.strip(),
        slug=body.slug,
        description=body.description,
        country_code=body.country_code.upper(),
        owner_user_id=principal.user_id,
    )
    session.add(organization)
    try:
        await session.flush()
        session.add(
            Membership(
                organization_id=organization.id,
                user_id=principal.user_id,
                role="admin",
                status="active",
            )
        )
        await session.commit()
        await session.refresh(organization)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Organisation slug is already in use"
        ) from exc
    return OrganizationRead.model_validate(organization)


@router.get("", response_model=list[OrganizationRead])
async def list_my_organizations(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OrganizationRead]:
    """List only organisations where the caller has an active membership."""
    result = await session.scalars(
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == principal.user_id, Membership.status == "active")
        .order_by(Organization.name)
    )
    return [OrganizationRead.model_validate(item) for item in result.all()]


class OwnershipTransfer(BaseModel):
    """Transfer organisation ownership to an active organisation member."""

    new_owner_user_id: str = Field(min_length=1, max_length=36)


@router.post("/{organization_id}/ownership-transfer")
async def transfer_organization_ownership(
    organization_id: str,
    body: OwnershipTransfer,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Atomically transfer ownership and preserve an active administrator."""
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")

    organization = await session.scalar(
        select(Organization)
        .where(Organization.id == organization_id)
        .with_for_update()
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    if organization.owner_user_id != principal.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the current organisation owner can transfer ownership",
        )
    if body.new_owner_user_id == principal.user_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The new owner must be a different organisation member",
        )

    new_owner_membership = await session.scalar(
        select(Membership)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.new_owner_user_id,
        )
        .with_for_update()
    )
    if new_owner_membership is None or new_owner_membership.status != "active":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The new owner must have an active organisation membership",
        )

    current_owner_membership = await session.scalar(
        select(Membership)
        .where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
        .with_for_update()
    )
    if current_owner_membership is None or current_owner_membership.status != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The current owner must retain an active membership during transfer",
        )

    previous_owner_id = organization.owner_user_id
    new_owner_membership.role = "admin"
    current_owner_membership.role = "programme_manager"
    organization.owner_user_id = body.new_owner_user_id
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=body.new_owner_user_id,
            action="organization.ownership_transferred",
            changes={
                "owner_user_id": {
                    "before": previous_owner_id,
                    "after": body.new_owner_user_id,
                }
            },
        )
    )

    await session.commit()
    return {
        "organization_id": organization_id,
        "previous_owner_user_id": previous_owner_id,
        "owner_user_id": body.new_owner_user_id,
        "transferred_at": datetime.now(UTC).isoformat(),
    }


@router.get("/{organization_id}/audit-events")
async def list_organization_audit_events(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, object]]:
    """List a bounded, tenant-scoped audit history for organisation administrators."""
    if membership.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Administrator role required",
        )
    rows = await session.scalars(
        select(OrganizationAuditEvent)
        .where(OrganizationAuditEvent.organization_id == organization_id)
        .order_by(OrganizationAuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": event.id,
            "action": event.action,
            "actor_user_id": event.actor_user_id,
            "subject_user_id": event.subject_user_id,
            "changes": event.changes,
            "created_at": event.created_at,
        }
        for event in rows.all()
    ]
