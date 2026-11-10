"""Organisation creation and membership-scoped discovery endpoints."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, Organization

from .dependencies import Principal, get_current_principal, get_session

router = APIRouter(prefix="/organizations", tags=["organizations"])
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
        raise HTTPException(status.HTTP_409_CONFLICT, "Organisation slug is already in use") from exc
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
