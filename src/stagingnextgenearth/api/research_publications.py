"""Study publication registry with DOI, ORCID and OpenAlex identifiers."""

import re
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchPublication,
    ResearchStudy,
    ResearchStudyCollaborator,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}/publications",
    tags=["research-publications"],
)
_WRITE_ROLES = {"editor", "contributor"}
_REVIEW_ROLES = {"admin", "programme_manager"}
_ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[^\s]+$", re.IGNORECASE)
_OPENALEX_PATTERN = re.compile(r"^W\d+$")


class PublicationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    authors: list[str] = Field(min_length=1, max_length=100)
    author_orcids: list[str] = Field(default_factory=list, max_length=100)
    publication_type: Literal[
        "article", "book", "chapter", "conference_paper", "report", "preprint", "other"
    ]
    journal_or_venue: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=240)
    published_on: date | None = None
    doi: str | None = Field(default=None, max_length=255)
    openalex_id: str | None = Field(default=None, max_length=32)
    url: str | None = Field(default=None, max_length=2000)
    abstract: str | None = Field(default=None, max_length=20000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Publication title cannot be blank")
        return cleaned

    @field_validator("authors")
    @classmethod
    def validate_authors(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Author names cannot be blank")
        return cleaned

    @field_validator("author_orcids")
    @classmethod
    def validate_orcids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().removeprefix("https://orcid.org/") for value in values]
        if any(not _ORCID_PATTERN.fullmatch(value) for value in cleaned):
            raise ValueError("ORCID identifiers must use the 0000-0000-0000-0000 format")
        for value in cleaned:
            digits = value.replace("-", "")
            total = 0
            for digit in digits[:15]:
                total = (total + int(digit)) * 2
            remainder = (12 - (total % 11)) % 11
            expected = "X" if remainder == 10 else str(remainder)
            if digits[-1] != expected:
                raise ValueError("ORCID checksum is invalid")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Author ORCID identifiers must be unique")
        return cleaned

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.lower().startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        if not _DOI_PATTERN.fullmatch(normalized):
            raise ValueError("DOI must be a valid DOI name or doi.org URL")
        return normalized.lower()

    @field_validator("openalex_id")
    @classmethod
    def validate_openalex_id(cls, value: str | None) -> str | None:
        if value is not None:
            normalized = value.strip().removeprefix("https://openalex.org/")
            if not _OPENALEX_PATTERN.fullmatch(normalized):
                raise ValueError("OpenAlex work identifiers must have the form W1234567890")
            return normalized
        return None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is not None:
            cleaned = value.strip()
            parsed = urlparse(cleaned)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("URL must be an absolute HTTP or HTTPS URL")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("URL cannot contain embedded credentials")
            return cleaned
        return None


class PublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    title: str
    authors: list[str]
    author_orcids: list[str]
    publication_type: str
    journal_or_venue: str | None
    publisher: str | None
    published_on: date | None
    doi: str | None
    openalex_id: str | None
    url: str | None
    abstract: str | None
    created_at: datetime


async def _study(session: AsyncSession, organization_id: str, study_id: str) -> ResearchStudy:
    study = await session.scalar(select(ResearchStudy).where(
        ResearchStudy.id == study_id,
        ResearchStudy.organization_id == organization_id,
    ))
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    return study


async def _study_role(
    session: AsyncSession, study: ResearchStudy, principal: Principal, membership: Membership
) -> str:
    if membership.role == "admin" or study.lead_researcher_id == principal.user_id:
        return "editor"
    if membership.role in _REVIEW_ROLES:
        return "reviewer"
    collaborator = await session.scalar(select(ResearchStudyCollaborator).where(
        ResearchStudyCollaborator.study_id == study.id,
        ResearchStudyCollaborator.organization_id == study.organization_id,
        ResearchStudyCollaborator.user_id == principal.user_id,
        ResearchStudyCollaborator.status == "active",
    ))
    if collaborator is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study access required")
    return collaborator.role


@router.post("", response_model=PublicationRead, status_code=status.HTTP_201_CREATED)
async def create_publication(
    organization_id: str,
    study_id: str,
    body: PublicationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicationRead:
    study = await _study(session, organization_id, study_id)
    if await _study_role(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Publication authoring permission required")
    publication = ResearchPublication(
        study_id=study_id,
        title=body.title.strip(),
        authors=body.authors,
        author_orcids=body.author_orcids,
        publication_type=body.publication_type,
        journal_or_venue=body.journal_or_venue.strip() if body.journal_or_venue else None,
        publisher=body.publisher.strip() if body.publisher else None,
        published_on=body.published_on,
        doi=body.doi,
        openalex_id=body.openalex_id,
        url=body.url,
        abstract=body.abstract.strip() if body.abstract else None,
        created_by=principal.user_id,
    )
    session.add(publication)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        original_error = exc.orig
        constraint_name = getattr(getattr(original_error, "diag", None), "constraint_name", None)
        sqlite_duplicate = (
            "UNIQUE constraint failed: research_publications.study_id, research_publications.doi"
            in str(original_error)
        )
        if constraint_name == "uq_research_publication_study_doi" or sqlite_duplicate:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "A publication with this DOI is already registered for the study",
            ) from exc
        raise
    await session.refresh(publication)
    return PublicationRead.model_validate(publication)


@router.get("", response_model=list[PublicationRead])
async def list_publications(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicationRead]:
    study = await _study(session, organization_id, study_id)
    await _study_role(session, study, principal, membership)
    result = await session.scalars(select(ResearchPublication).where(
        ResearchPublication.study_id == study_id
    ).order_by(ResearchPublication.published_on.desc(), ResearchPublication.created_at.desc()))
    return [PublicationRead.model_validate(item) for item in result.all()]
