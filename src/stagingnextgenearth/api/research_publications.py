"""Study publication registry with DOI, ORCID and OpenAlex identifiers."""

import hashlib
import json
import re
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchPublication,
    ResearchPublicationMetadataSource,
    ResearchStudy,
    ResearchStudyCollaborator,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

PublicationType = Literal[
    "article", "book", "chapter", "conference_paper", "report", "preprint", "other"
]

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}/publications",
    tags=["research-publications"],
)
_WRITE_ROLES = {"editor", "contributor"}
_REVIEW_ROLES = {"admin", "programme_manager"}
_REFRESHABLE_FIELDS = (
    "title",
    "authors",
    "author_orcids",
    "publication_type",
    "journal_or_venue",
    "publisher",
    "published_on",
    "url",
    "abstract",
)
_ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[^\s]+$", re.IGNORECASE)
_OPENALEX_PATTERN = re.compile(r"^W\d+$")


class PublicationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    authors: list[str] = Field(min_length=1, max_length=100)
    author_orcids: list[str] = Field(default_factory=list, max_length=100)
    publication_type: PublicationType
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


_OPENALEX_API = "https://api.openalex.org/works/"
_OPENALEX_RESPONSE_LIMIT = 1_000_000


class PublicationMetadataPreview(BaseModel):
    """Normalized, unpersisted metadata returned by OpenAlex."""

    title: str
    authors: list[str]
    author_orcids: list[str]
    publication_type: Literal[
        "article", "book", "chapter", "conference_paper", "report", "preprint", "other"
    ]
    journal_or_venue: str | None = None
    publisher: str | None = None
    published_on: date | None = None
    doi: str | None = None
    openalex_id: str
    url: str | None = None
    abstract: str | None = None
    source: Literal["OpenAlex"] = "OpenAlex"



class PublicationMetadataImport(BaseModel):
    """Explicit import command; lookup remains a separate read-only operation."""

    doi: str | None = Field(default=None, min_length=5, max_length=255)
    openalex_id: str | None = Field(default=None, min_length=2, max_length=32)

    @model_validator(mode="after")
    def require_one_identifier(self) -> "PublicationMetadataImport":
        if (self.doi is None) == (self.openalex_id is None):
            raise ValueError("Supply exactly one of doi or openalex_id")
        return self



class PublicationMetadataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    publication_id: str
    provider: str
    provider_work_id: str
    source_url: str
    metadata_sha256: str
    imported_fields: list[str]
    metadata_snapshot: dict[str, object] | None = None
    imported_by: str
    fetched_at: datetime



class PublicationMetadataFieldChange(BaseModel):
    field: str
    current_value: object
    provider_value: object
    safe_to_apply: bool


class PublicationMetadataRefreshPreview(BaseModel):
    publication_id: str
    openalex_id: str
    changes: list[PublicationMetadataFieldChange]


class PublicationMetadataRefreshApply(BaseModel):
    fields: list[str] = Field(min_length=1, max_length=9)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Refresh fields must be unique")
        if any(value not in _REFRESHABLE_FIELDS for value in values):
            raise ValueError("One or more fields cannot be refreshed")
        return values


async def get_openalex_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide a bounded-timeout client without following external redirects."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, connect=2.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "NextGenForEarth/0.1 (publication metadata lookup)"},
    ) as client:
        yield client


def _abstract_from_inverted_index(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    words: dict[int, str] = {}
    for token, positions in value.items():
        if isinstance(token, str) and isinstance(positions, list):
            for position in positions:
                if isinstance(position, int) and 0 <= position < 100_000:
                    words[position] = token
    if not words:
        return None
    return " ".join(words[index] for index in sorted(words))


def _openalex_preview(record: dict[str, object]) -> PublicationMetadataPreview:
    title = record.get("title")
    identifier = record.get("id")
    if not isinstance(title, str) or not title.strip() or not isinstance(identifier, str):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAlex returned incomplete metadata")

    authors: list[str] = []
    orcids: list[str] = []
    authorships = record.get("authorships")
    if isinstance(authorships, list):
        for authorship in authorships[:100]:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if not isinstance(author, dict):
                continue
            name = author.get("display_name")
            if isinstance(name, str) and name.strip():
                authors.append(name.strip())
                orcid = author.get("orcid")
                if isinstance(orcid, str) and orcid.startswith("https://orcid.org/"):
                    orcid_value = orcid.removeprefix("https://orcid.org/")
                    if _ORCID_PATTERN.fullmatch(orcid_value):
                        orcids.append(orcid_value)

    primary_location = record.get("primary_location")
    source: dict[str, object] = {}
    if isinstance(primary_location, dict) and isinstance(primary_location.get("source"), dict):
        source = primary_location["source"]

    normalized_id = identifier.removeprefix("https://openalex.org/")
    if not _OPENALEX_PATTERN.fullmatch(normalized_id):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAlex returned an invalid work ID")

    doi_value = record.get("doi")
    doi = doi_value.removeprefix("https://doi.org/").lower() if isinstance(doi_value, str) else None
    work_type = record.get("type")
    type_map: dict[str, PublicationType] = {
        "article": "article",
        "book": "book",
        "book-chapter": "chapter",
        "proceedings-article": "conference_paper",
        "report": "report",
        "preprint": "preprint",
    }
    publication_type: PublicationType = type_map.get(str(work_type), "other")
    published_value = record.get("publication_date")
    published_on = None
    if isinstance(published_value, str):
        try:
            published_on = date.fromisoformat(published_value)
        except ValueError:
            published_on = None
    landing_page_value = record.get("landing_page_url")
    landing_page = None
    if isinstance(landing_page_value, str):
        try:
            parsed_landing_page = urlparse(landing_page_value)
        except ValueError:
            parsed_landing_page = None
        if (
            parsed_landing_page is not None
            and parsed_landing_page.scheme in {"http", "https"}
            and parsed_landing_page.hostname
            and parsed_landing_page.username is None
            and parsed_landing_page.password is None
        ):
            landing_page = landing_page_value[:2000]
    venue = source.get("display_name")
    publisher = source.get("host_organization_name")
    return PublicationMetadataPreview(
        title=title.strip()[:500],
        authors=authors,
        author_orcids=list(dict.fromkeys(orcids)),
        publication_type=publication_type,
        journal_or_venue=venue[:300] if isinstance(venue, str) else None,
        publisher=publisher[:240] if isinstance(publisher, str) else None,
        published_on=published_on,
        doi=doi if isinstance(doi, str) and _DOI_PATTERN.fullmatch(doi) else None,
        openalex_id=normalized_id,
        url=landing_page,
        abstract=_abstract_from_inverted_index(record.get("abstract_inverted_index")),
    )



def _validate_openalex_match(
    preview: PublicationMetadataPreview, requested_identifier: str
) -> None:
    if requested_identifier.startswith("https://doi.org/"):
        requested_doi = requested_identifier.removeprefix("https://doi.org/").lower()
        if preview.doi != requested_doi:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "OpenAlex response does not match the requested DOI",
            )
    elif preview.openalex_id != requested_identifier:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "OpenAlex response does not match the requested work ID",
        )


async def _read_openalex_response(
    client: httpx.AsyncClient, identifier: str
) -> dict[str, object]:
    url = _OPENALEX_API + quote(identifier, safe="/:")
    try:
        async with client.stream("GET", url) as response:
            if response.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching OpenAlex work found")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAlex rate limit reached"
                )
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAlex metadata service is unavailable"
                )
            declared_length = response.headers.get("content-length")
            if declared_length:
                try:
                    if int(declared_length) > _OPENALEX_RESPONSE_LIMIT:
                        raise HTTPException(
                            status.HTTP_502_BAD_GATEWAY, "OpenAlex response exceeds size limit"
                        )
                except ValueError:
                    pass
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > _OPENALEX_RESPONSE_LIMIT:
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY, "OpenAlex response exceeds size limit"
                    )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAlex metadata request timed out"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAlex metadata request failed"
        ) from exc
    try:
        result = httpx.Response(200, content=bytes(payload)).json()
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAlex returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "OpenAlex returned an invalid record")
    return result


@router.get("/metadata/lookup", response_model=PublicationMetadataPreview)
async def lookup_publication_metadata(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_openalex_client)],
    doi: str | None = Query(default=None, min_length=5, max_length=255),
    openalex_id: str | None = Query(default=None, min_length=2, max_length=32),
) -> PublicationMetadataPreview:
    """Preview metadata by DOI or OpenAlex ID; never writes to the registry."""
    study = await _study(session, organization_id, study_id)
    await _study_role(session, study, principal, membership)
    if (doi is None) == (openalex_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Supply exactly one of doi or openalex_id"
        )
    if doi is not None:
        normalized = doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.lower().startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        if not _DOI_PATTERN.fullmatch(normalized):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid DOI")
        identifier = "https://doi.org/" + normalized
    else:
        normalized = (openalex_id or "").strip().removeprefix("https://openalex.org/")
        if not _OPENALEX_PATTERN.fullmatch(normalized):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid OpenAlex work ID")
        identifier = normalized
    record = await _read_openalex_response(client, identifier)
    preview = _openalex_preview(record)
    _validate_openalex_match(preview, identifier)
    return preview



@router.post(
    "/metadata/import",
    response_model=PublicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_publication_metadata(
    organization_id: str,
    study_id: str,
    body: PublicationMetadataImport,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_openalex_client)],
) -> PublicationRead:
    """Create a publication from a fresh provider response and record its provenance."""
    study = await _study(session, organization_id, study_id)
    if await _study_role(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Publication authoring permission required")

    if body.doi is not None:
        normalized = body.doi.strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.lower().startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        if not _DOI_PATTERN.fullmatch(normalized):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid DOI")
        identifier = "https://doi.org/" + normalized
    else:
        normalized = (body.openalex_id or "").strip().removeprefix("https://openalex.org/")
        if not _OPENALEX_PATTERN.fullmatch(normalized):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid OpenAlex work ID")
        identifier = normalized

    record = await _read_openalex_response(client, identifier)
    preview = _openalex_preview(record)
    _validate_openalex_match(preview, identifier)
    duplicate_filters = [ResearchPublication.openalex_id == preview.openalex_id]
    if preview.doi is not None:
        duplicate_filters.append(ResearchPublication.doi == preview.doi)
    existing = await session.scalar(
        select(ResearchPublication).where(
            ResearchPublication.study_id == study_id,
            or_(*duplicate_filters),
        )
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This OpenAlex work or DOI is already registered for the study",
        )

    publication = ResearchPublication(
        study_id=study_id,
        title=preview.title,
        authors=preview.authors,
        author_orcids=preview.author_orcids,
        publication_type=preview.publication_type,
        journal_or_venue=preview.journal_or_venue,
        publisher=preview.publisher,
        published_on=preview.published_on,
        doi=preview.doi,
        openalex_id=preview.openalex_id,
        url=preview.url,
        abstract=preview.abstract,
        created_by=principal.user_id,
    )
    serialized = json.dumps(
        preview.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    provenance = ResearchPublicationMetadataSource(
        provider="openalex",
        provider_work_id=preview.openalex_id,
        source_url=f"https://openalex.org/{preview.openalex_id}",
        metadata_sha256=hashlib.sha256(serialized).hexdigest(),
        metadata_snapshot=preview.model_dump(mode="json", exclude={"source"}),
        imported_fields=[
            "title",
            "authors",
            "author_orcids",
            "publication_type",
            "journal_or_venue",
            "publisher",
            "published_on",
            "doi",
            "openalex_id",
            "url",
            "abstract",
        ],
        imported_by=principal.user_id,
    )
    session.add(publication)
    await session.flush()
    provenance.publication_id = publication.id
    session.add(provenance)
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




def _publication_metadata_snapshot(publication: ResearchPublication) -> dict[str, object]:
    return {
        "title": publication.title,
        "authors": publication.authors,
        "author_orcids": publication.author_orcids,
        "publication_type": publication.publication_type,
        "journal_or_venue": publication.journal_or_venue,
        "publisher": publication.publisher,
        "published_on": publication.published_on.isoformat()
        if publication.published_on is not None
        else None,
        "doi": publication.doi,
        "openalex_id": publication.openalex_id,
        "url": publication.url,
        "abstract": publication.abstract,
    }


async def _fresh_publication_preview(
    publication: ResearchPublication, client: httpx.AsyncClient
) -> PublicationMetadataPreview:
    if publication.openalex_id:
        identifier = publication.openalex_id
    elif publication.doi:
        identifier = "https://doi.org/" + publication.doi
    else:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Publication has no OpenAlex ID or DOI and cannot be refreshed",
        )
    record = await _read_openalex_response(client, identifier)
    preview = _openalex_preview(record)
    _validate_openalex_match(preview, identifier)
    return preview


@router.get(
    "/{publication_id}/metadata/sources",
    response_model=list[PublicationMetadataSourceRead],
)
async def list_publication_metadata_sources(
    organization_id: str,
    study_id: str,
    publication_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicationMetadataSourceRead]:
    """Return immutable provider-import provenance for an accessible publication."""
    study = await _study(session, organization_id, study_id)
    await _study_role(session, study, principal, membership)
    publication = await session.scalar(
        select(ResearchPublication).where(
            ResearchPublication.id == publication_id,
            ResearchPublication.study_id == study_id,
        )
    )
    if publication is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication not found")
    result = await session.scalars(
        select(ResearchPublicationMetadataSource)
        .where(ResearchPublicationMetadataSource.publication_id == publication_id)
        .order_by(ResearchPublicationMetadataSource.fetched_at.desc())
    )
    return [PublicationMetadataSourceRead.model_validate(item) for item in result.all()]



@router.get(
    "/{publication_id}/metadata/refresh-preview",
    response_model=PublicationMetadataRefreshPreview,
)
async def preview_publication_metadata_refresh(
    organization_id: str,
    study_id: str,
    publication_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_openalex_client)],
) -> PublicationMetadataRefreshPreview:
    """Compare current publication values with a fresh provider response."""
    study = await _study(session, organization_id, study_id)
    await _study_role(session, study, principal, membership)
    publication = await session.scalar(
        select(ResearchPublication).where(
            ResearchPublication.id == publication_id,
            ResearchPublication.study_id == study_id,
        )
    )
    if publication is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication not found")
    preview = await _fresh_publication_preview(publication, client)
    latest_source = await session.scalar(
        select(ResearchPublicationMetadataSource)
        .where(ResearchPublicationMetadataSource.publication_id == publication_id)
        .order_by(ResearchPublicationMetadataSource.fetched_at.desc())
        .limit(1)
    )
    baseline = latest_source.metadata_snapshot if latest_source is not None else None
    current = _publication_metadata_snapshot(publication)
    provider_values = preview.model_dump(mode="json", exclude={"source"})
    changes = [
        PublicationMetadataFieldChange(
            field=field,
            current_value=current[field],
            provider_value=provider_values[field],
            safe_to_apply=baseline is not None
            and field in baseline
            and current[field] == baseline[field],
        )
        for field in _REFRESHABLE_FIELDS
        if current[field] != provider_values[field]
    ]
    return PublicationMetadataRefreshPreview(
        publication_id=publication_id,
        openalex_id=preview.openalex_id,
        changes=changes,
    )


@router.post(
    "/{publication_id}/metadata/refresh",
    response_model=PublicationRead,
)
async def apply_publication_metadata_refresh(
    organization_id: str,
    study_id: str,
    publication_id: str,
    body: PublicationMetadataRefreshApply,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_openalex_client)],
) -> PublicationRead:
    """Apply selected provider changes only where local values remain unmodified."""
    study = await _study(session, organization_id, study_id)
    if await _study_role(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Publication authoring permission required")
    publication = await session.scalar(
        select(ResearchPublication)
        .where(
            ResearchPublication.id == publication_id,
            ResearchPublication.study_id == study_id,
        )
        .with_for_update()
    )
    if publication is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication not found")
    latest_source = await session.scalar(
        select(ResearchPublicationMetadataSource)
        .where(ResearchPublicationMetadataSource.publication_id == publication_id)
        .order_by(ResearchPublicationMetadataSource.fetched_at.desc())
        .limit(1)
    )
    baseline = latest_source.metadata_snapshot if latest_source is not None else None
    if baseline is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No field baseline exists; automatic refresh is disabled for this publication",
        )
    preview = await _fresh_publication_preview(publication, client)
    current = _publication_metadata_snapshot(publication)
    provider_values = preview.model_dump(mode="json", exclude={"source"})
    for field in body.fields:
        if field not in baseline or current[field] != baseline[field]:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Field '{field}' was edited locally and will not be overwritten",
            )
        if current[field] == provider_values[field]:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Field '{field}' has no provider change to apply",
            )
    for field in body.fields:
        setattr(publication, field, getattr(preview, field))
    updated_snapshot = _publication_metadata_snapshot(publication)
    serialized = json.dumps(
        provider_values, sort_keys=True, separators=(",", ":")
    ).encode()
    provenance = ResearchPublicationMetadataSource(
        publication_id=publication.id,
        provider="openalex",
        provider_work_id=preview.openalex_id,
        source_url=f"https://openalex.org/{preview.openalex_id}",
        metadata_sha256=hashlib.sha256(serialized).hexdigest(),
        metadata_snapshot=updated_snapshot,
        imported_fields=body.fields,
        imported_by=principal.user_id,
    )
    session.add(provenance)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The metadata refresh conflicts with another update; reload and compare again",
        ) from None
    await session.refresh(publication)
    return PublicationRead.model_validate(publication)
