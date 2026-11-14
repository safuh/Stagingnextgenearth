"""Organisation people directory with moderated public publication."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, OrganizationPerson

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(tags=["organisation-directory"])
PERSON_TYPES = {
    "employee", "board_member", "executive", "volunteer", "ambassador",
    "researcher", "mentor", "advisor", "intern", "trainee", "consultant", "alumnus",
}


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    biography: str | None = Field(default=None, max_length=5000)
    positions: list[str] = Field(default_factory=list, max_length=12)
    person_types: list[str] = Field(default_factory=list, max_length=12)
    country_code: str = Field(default="KE", min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=120)
    profile_image_url: str | None = Field(default=None, max_length=1000)
    website_url: str | None = Field(default=None, max_length=1000)
    source_url: str | None = Field(default=None, max_length=1000)
    source_label: str | None = Field(default="NextGen For Earth website", max_length=160)


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    biography: str | None = Field(default=None, max_length=5000)
    positions: list[str] | None = Field(default=None, max_length=12)
    person_types: list[str] | None = Field(default=None, max_length=12)
    country_code: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=120)
    profile_image_url: str | None = Field(default=None, max_length=1000)
    website_url: str | None = Field(default=None, max_length=1000)
    source_url: str | None = Field(default=None, max_length=1000)
    source_label: str | None = Field(default=None, max_length=160)
    review_state: str | None = Field(default=None, pattern=r"^(pending|verified|rejected)$")
    visibility: str | None = Field(default=None, pattern=r"^(private|internal|public)$")
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    full_name: str
    biography: str | None
    positions: list[str]
    person_types: list[str]
    country_code: str
    region: str | None
    profile_image_url: str | None
    website_url: str | None
    source_url: str | None
    source_label: str | None
    review_state: str
    visibility: str
    status: str


class PublicPersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    biography: str | None
    positions: list[str]
    person_types: list[str]
    country_code: str
    region: str | None
    profile_image_url: str | None
    website_url: str | None


def _require_admin(membership: Membership) -> None:
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")


def _validate_person_types(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(value.strip().lower() for value in values))
    if any(value not in PERSON_TYPES for value in normalized):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported person type")
    return normalized


def _validate_positions(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if any(len(value) > 120 for value in normalized):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Position titles must be 120 characters or fewer")
    return normalized


@router.get("/organizations/{organization_id}/people", response_model=list[PersonRead])
async def list_people(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PersonRead]:
    """List the full directory to administrators only."""
    _require_admin(membership)
    rows = await session.scalars(
        select(OrganizationPerson)
        .where(OrganizationPerson.organization_id == organization_id)
        .order_by(OrganizationPerson.full_name)
    )
    return [PersonRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/people",
    response_model=PersonRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_person(
    organization_id: str,
    body: PersonCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PersonRead:
    """Create a directory profile without creating or implying a login account."""
    _require_admin(membership)
    person = OrganizationPerson(
        organization_id=organization_id,
        full_name=body.full_name.strip(),
        biography=body.biography,
        positions=_validate_positions(body.positions),
        person_types=_validate_person_types(body.person_types),
        country_code=body.country_code.upper(),
        region=body.region,
        profile_image_url=body.profile_image_url,
        website_url=body.website_url,
        source_url=body.source_url,
        source_label=body.source_label,
        created_by=principal.user_id,
        updated_by=principal.user_id,
    )
    session.add(person)
    await session.flush()
    await session.commit()
    await session.refresh(person)
    return PersonRead.model_validate(person)


@router.patch("/organizations/{organization_id}/people/{person_id}", response_model=PersonRead)
async def update_person(
    organization_id: str,
    person_id: str,
    body: PersonUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PersonRead:
    """Edit a profile and explicitly control verification/publication state."""
    _require_admin(membership)
    person = await session.scalar(
        select(OrganizationPerson).where(
            OrganizationPerson.id == person_id,
            OrganizationPerson.organization_id == organization_id,
        )
    )
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Directory profile not found")
    changes = body.model_dump(exclude_unset=True)
    if "person_types" in changes and changes["person_types"] is not None:
        changes["person_types"] = _validate_person_types(changes["person_types"])
    if "positions" in changes and changes["positions"] is not None:
        changes["positions"] = _validate_positions(changes["positions"])
    if "country_code" in changes and changes["country_code"] is not None:
        changes["country_code"] = changes["country_code"].upper()
    for field, value in changes.items():
        if value is not None or field in {"biography", "region", "profile_image_url", "website_url", "source_url", "source_label"}:
            setattr(person, field, value)
    person.updated_by = principal.user_id
    await session.commit()
    await session.refresh(person)
    return PersonRead.model_validate(person)


@router.get("/public/organizations/{organization_slug}/people", response_model=list[PublicPersonRead])
async def list_public_people(
    organization_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicPersonRead]:
    """Expose only active, verified, explicitly public directory profiles."""
    from stagingnextgenearth.platform.models import Organization

    organization = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    rows = await session.scalars(
        select(OrganizationPerson)
        .where(
            OrganizationPerson.organization_id == organization.id,
            OrganizationPerson.review_state == "verified",
            OrganizationPerson.visibility == "public",
            OrganizationPerson.status == "active",
        )
        .order_by(OrganizationPerson.full_name)
    )
    return [PublicPersonRead.model_validate(row) for row in rows.all()]
