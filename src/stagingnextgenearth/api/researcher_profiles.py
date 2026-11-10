"""Authenticated self-service researcher profile endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import ResearcherProfile

from .dependencies import Principal, get_current_principal, get_session

router = APIRouter(prefix="/me/researcher-profile", tags=["researcher-profiles"])


class ResearcherProfileUpsert(BaseModel):
    """Professional profile data owned by the authenticated account."""

    display_name: str = Field(min_length=1, max_length=120)
    biography: str | None = Field(default=None, max_length=2000)
    affiliation: str | None = Field(default=None, max_length=200)
    orcid: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$",
        max_length=19,
    )
    website_url: str | None = Field(default=None, max_length=500)
    research_interests: list[str] = Field(default_factory=list, max_length=30)
    visibility: Literal["private", "organization"] = "private"

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name cannot be blank")
        return cleaned

    @field_validator("research_interests")
    @classmethod
    def normalize_interests(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("research interests cannot be blank")
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("research interests cannot exceed 80 characters")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("research interests must be unique")
        return cleaned

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, value: str | None) -> str | None:
        if value is not None:
            cleaned = value.strip()
            if not cleaned.startswith(("https://", "http://")):
                raise ValueError("website_url must use http or https")
            return cleaned
        return value


class ResearcherProfileRead(BaseModel):
    """Public-safe profile fields; account credentials and identifiers are excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    display_name: str
    biography: str | None
    affiliation: str | None
    orcid: str | None
    website_url: str | None
    research_interests: list[str]
    visibility: str


@router.get("", response_model=ResearcherProfileRead)
async def get_my_researcher_profile(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearcherProfileRead:
    """Read only the authenticated user's profile."""
    profile = await session.scalar(
        select(ResearcherProfile).where(ResearcherProfile.user_id == principal.user_id)
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Researcher profile not found")
    return ResearcherProfileRead.model_validate(profile)


@router.put("", response_model=ResearcherProfileRead)
async def upsert_my_researcher_profile(
    body: ResearcherProfileUpsert,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearcherProfileRead:
    """Create or replace the authenticated user's profile; no user ID is accepted."""
    profile = await session.scalar(
        select(ResearcherProfile).where(ResearcherProfile.user_id == principal.user_id)
    )
    values = body.model_dump()
    if profile is None:
        profile = ResearcherProfile(user_id=principal.user_id, **values)
        session.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)

    try:
        await session.commit()
        await session.refresh(profile)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The supplied ORCID is already associated with another profile",
        ) from exc
    return ResearcherProfileRead.model_validate(profile)
