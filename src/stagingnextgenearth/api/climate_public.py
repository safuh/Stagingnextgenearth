# ruff: noqa: E501, I001
"""Governed public climate release lifecycle and anonymous read API."""

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder

from stagingnextgenearth.core.config import DeploymentStage, Settings
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from stagingnextgenearth.platform.climate_public import (
    ClimatePublicRelease,
    ClimatePublicReleaseEvent,
)
from stagingnextgenearth.platform.models import (
    ClimateIngestionRun,
    ClimateObservation,
    Membership,
    Organization,
    PublicContentEntry,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["public-climate"])
_RELEASE_ROLES = {"admin", "founder", "executive", "researcher"}
_REVIEW_ROLES = {"admin", "founder", "executive", "programme_manager"}
_DATA_CLASSES = {
    "station_observation", "satellite_estimate", "reanalysis", "forecast", "projection",
    "synthetic_demo",
}


_PUBLIC_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"


def _public_cache_response(
    request: Request,
    response: Response,
    payload: object,
) -> Response | None:
    """Attach a representation-specific ETag and honour conditional GET requests."""
    encoded = json.dumps(
        jsonable_encoder(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    etag = f'"{hashlib.sha256(encoded.encode("utf-8")).hexdigest()}"'
    headers = {"ETag": etag, "Cache-Control": _PUBLIC_CACHE_CONTROL}
    response.headers.update(headers)
    candidates = {
        value.strip().removeprefix("W/")
        for value in request.headers.get("if-none-match", "").split(",")
        if value.strip()
    }
    if "*" in candidates or etag in candidates:
        return Response(status_code=304, headers=headers)
    return None


def _public_release_filters(
    organization_id: str, settings: Settings
) -> tuple[ColumnElement[bool], ...]:
    """Keep synthetic fixtures out of production public responses, even if copied."""
    filters: list[ColumnElement[bool]] = [
        ClimatePublicRelease.organization_id == organization_id,
        ClimatePublicRelease.state == "published",
    ]
    if (
        settings.deployment_stage is DeploymentStage.PRODUCTION
        or not settings.climate_demo_publication_allowed
    ):
        filters.extend([
            ClimatePublicRelease.provider_id != "demo-synthetic",
            ClimatePublicRelease.data_class != "synthetic_demo",
        ])
    return tuple(filters)


class ClimateSeriesPoint(BaseModel):
    observed_at: datetime
    value: float

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("series timestamps must include a timezone")
        return value


class ClimateRegionValue(BaseModel):
    region: str = Field(min_length=1, max_length=120)
    value: float
    coverage_pct: float | None = Field(default=None, ge=0, le=100)


class ClimateReleaseCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=3, max_length=240)
    summary: str = Field(min_length=10, max_length=4000)
    provider_id: Literal["nasa-power", "chirps-v3", "copernicus-era5"]
    data_class: Literal["station_observation", "satellite_estimate", "reanalysis", "forecast", "projection"]
    geography_label: str = Field(min_length=2, max_length=200)
    geography_resolution: str = Field(min_length=2, max_length=120)
    period_start: datetime
    period_end: datetime
    baseline: str | None = Field(default=None, max_length=200)
    uncertainty_summary: str | None = Field(default=None, max_length=4000)
    limitations: str = Field(min_length=5, max_length=4000)
    terms_url: HttpUrl | None = None
    citation_url: HttpUrl | None = None
    source_ingestion_run_id: str

    @field_validator("geography_label")
    @classmethod
    def reject_precise_coordinate_labels(cls, value: str) -> str:
        if re.search(r"-?\d{1,3}\.\d+\s*[,/]\s*-?\d{1,3}\.\d+", value):
            raise ValueError("public geography labels must not contain precise coordinate pairs")
        return value

    @field_validator("period_start", "period_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("period timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_period(self) -> "ClimateReleaseCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        return self


class ClimateReleaseSummary(BaseModel):
    id: str
    slug: str
    version: int
    title: str
    summary: str
    indicator: str
    unit: str
    provider_id: str
    provider_product: str
    data_class: str
    geography_label: str
    geography_resolution: str
    period_start: datetime
    period_end: datetime
    baseline: str | None
    coverage_pct: float | None
    missingness_pct: float | None
    license_name: str
    attribution: str
    citation_url: str | None
    published_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ClimateReleaseDetail(ClimateReleaseSummary):
    provider_version: str | None
    aggregation_method: str
    uncertainty_summary: str | None
    limitations: str
    terms_url: str | None


class ClimateReleaseSeries(BaseModel):
    release: ClimateReleaseDetail
    series: list[ClimateSeriesPoint]
    regions: list[ClimateRegionValue]


class ClimateSourceRead(BaseModel):
    provider_id: str
    provider_product: str
    data_class: str
    license_name: str
    attribution: str
    terms_url: str | None
    citation_url: str | None
    release_count: int


class ClimateInsightRead(BaseModel):
    """Public editorial context linked to a published release and publication."""

    id: str
    slug: str
    title: str
    summary: str | None
    body: str | None
    region: str | None
    indicator: str | None
    evidence_note: str | None
    release_slug: str
    publication_title: str
    publication_url: str | None
    published_at: datetime | None


class ClimateReleaseWorkspaceRead(ClimateReleaseDetail):
    """Authenticated release view with workflow ownership and provenance references."""

    state: str
    created_by: str
    reviewed_by: str | None
    published_by: str | None
    source_ingestion_run_id: str | None
    licence_reviewed_by: str | None = None
    licence_reviewed_at: datetime | None = None
    licence_review_note: str | None = None


class ClimateReleaseAction(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ClimateReleaseLicenceReview(BaseModel):
    """Explicit evidence that a reviewer checked public-use and attribution terms."""

    licence_terms_confirmed: bool
    provider_terms_confirmed: bool
    attribution_confirmed: bool
    citation_confirmed: bool
    note: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def require_all_checks(self) -> "ClimateReleaseLicenceReview":
        if not all((
            self.licence_terms_confirmed,
            self.provider_terms_confirmed,
            self.attribution_confirmed,
            self.citation_confirmed,
        )):
            raise ValueError("Every licence, terms, attribution and citation check must be confirmed")
        if len(self.note.strip()) < 10:
            raise ValueError("A substantive licence review note is required")
        return self


def _summary(row: ClimatePublicRelease) -> ClimateReleaseSummary:
    return ClimateReleaseSummary.model_validate(row)


def _event(
    session: AsyncSession,
    row: ClimatePublicRelease,
    actor_id: str,
    action: str,
    from_state: str | None,
    to_state: str,
    note: str | None = None,
) -> ClimatePublicReleaseEvent:
    event = ClimatePublicReleaseEvent(
        organization_id=row.organization_id,
        release_id=row.id,
        actor_user_id=actor_id,
        action=action,
        from_state=from_state,
        to_state=to_state,
        note=note,
    )
    session.add(event)
    return event


async def _latest_licence_review(
    session: AsyncSession, release_id: str
) -> ClimatePublicReleaseEvent | None:
    return await session.scalar(
        select(ClimatePublicReleaseEvent)
        .where(
            ClimatePublicReleaseEvent.release_id == release_id,
            ClimatePublicReleaseEvent.action == "licence_reviewed",
        )
        .order_by(ClimatePublicReleaseEvent.created_at.desc())
        .limit(1)
    )


async def _release_source_run(
    session: AsyncSession, row: ClimatePublicRelease
) -> ClimateIngestionRun:
    if row.source_ingestion_run_id is None:
        raise HTTPException(409, "The source ingestion run is no longer available")
    source_run = await session.scalar(
        select(ClimateIngestionRun).where(
            ClimateIngestionRun.id == row.source_ingestion_run_id,
            ClimateIngestionRun.organization_id == row.organization_id,
        )
    )
    if source_run is None:
        raise HTTPException(409, "The source ingestion run is no longer available")
    return source_run


async def _quality_reviewers_for_run(
    session: AsyncSession, organization_id: str, ingestion_run_id: str
) -> set[str]:
    reviewer_ids = await session.scalars(
        select(ClimateObservation.reviewed_by)
        .where(
            ClimateObservation.organization_id == organization_id,
            ClimateObservation.ingestion_run_id == ingestion_run_id,
            ClimateObservation.reviewed_by.is_not(None),
        )
        .distinct()
    )
    return {reviewer_id for reviewer_id in reviewer_ids.all() if reviewer_id is not None}


async def _quality_reviewers(
    session: AsyncSession, row: ClimatePublicRelease
) -> set[str]:
    if row.source_ingestion_run_id is None:
        return set()
    return await _quality_reviewers_for_run(
        session, row.organization_id, row.source_ingestion_run_id
    )


def _workspace_read(
    row: ClimatePublicRelease,
    licence_event: ClimatePublicReleaseEvent | None = None,
) -> ClimateReleaseWorkspaceRead:
    review_note = None
    if licence_event is not None and licence_event.note:
        try:
            payload = json.loads(licence_event.note)
        except (TypeError, ValueError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("review_note"), str):
            review_note = payload["review_note"]
    return ClimateReleaseWorkspaceRead.model_validate(row).model_copy(
        update={
            "licence_reviewed_by": licence_event.actor_user_id if licence_event else None,
            "licence_reviewed_at": licence_event.created_at if licence_event else None,
            "licence_review_note": review_note,
        }
    )


def _licence_review_is_complete(event: ClimatePublicReleaseEvent) -> bool:
    try:
        payload = json.loads(event.note or "")
    except (TypeError, ValueError):
        return False
    checks = payload.get("checks") if isinstance(payload, dict) else None
    expected = {
        "licence_terms": True,
        "provider_terms": True,
        "attribution": True,
        "citation": True,
    }
    return checks == expected


@router.post(
    "/organizations/{organization_id}/climate-public-releases",
    response_model=ClimateReleaseWorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_release(
    organization_id: str,
    body: ClimateReleaseCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    if not await membership_has_any_role(session, membership, _RELEASE_ROLES):
        raise HTTPException(403, "Climate release authoring is not permitted")
    source_run = await session.scalar(select(ClimateIngestionRun).where(
        ClimateIngestionRun.id == body.source_ingestion_run_id,
        ClimateIngestionRun.organization_id == organization_id,
    ))
    if (
        source_run is None
        or source_run.status != "completed"
        or source_run.provider_id != body.provider_id
        or source_run.records_inserted < 1
    ):
        raise HTTPException(
            422,
            "A completed, same-organisation provider ingestion with inserted records is required",
        )
    if (
        not source_run.requested_area
        or "point" in source_run.requested_area
        or not {"west", "south", "east", "north"}.issubset(source_run.requested_area)
    ):
        raise HTTPException(
            422,
            "Public releases require a bounded-area ingestion; point requests are not publishable",
        )
    if source_run.provider_id != "chirps-v3":
        raise HTTPException(
            422,
            "This public release workflow currently supports CHIRPS v3 area products only",
        )
    area_label = source_run.requested_area.get("label")
    product_variant = source_run.requested_area.get("product_variant")
    if not isinstance(area_label, str) or body.geography_label != area_label:
        raise HTTPException(
            422,
            "The public geography label must match the label recorded with the provider request",
        )
    expected_data_class = {
        "sat": "satellite_estimate",
        "rnl": "reanalysis",
    }.get(str(product_variant))
    if expected_data_class is None or body.data_class != expected_data_class:
        raise HTTPException(
            422,
            "The release data class must match the CHIRPS product variant recorded at ingestion",
        )
    expected_resolution = "0.05° CHIRPS grid; arithmetic mean per day"
    if body.geography_resolution != expected_resolution:
        raise HTTPException(
            422,
            "The public resolution label must match the CHIRPS grid and aggregation method",
        )
    observation_filter = (
        ClimateObservation.organization_id == organization_id,
        ClimateObservation.ingestion_run_id == source_run.id,
    )
    observation_count = await session.scalar(
        select(func.count(ClimateObservation.id)).where(*observation_filter)
    )
    verified_count = await session.scalar(
        select(func.count(ClimateObservation.id)).where(
            *observation_filter,
            ClimateObservation.quality_status == "verified",
            ClimateObservation.reviewed_by.is_not(None),
            ClimateObservation.reviewed_by != ClimateObservation.created_by,
        )
    )
    if observation_count != source_run.records_inserted or verified_count != observation_count:
        raise HTTPException(
            409,
            "Every inserted observation in the provider run must pass independent quality review",
        )
    quality_reviewers = await _quality_reviewers_for_run(
        session, organization_id, source_run.id
    )
    if principal.user_id in quality_reviewers:
        raise HTTPException(
            403,
            "An observation quality reviewer cannot author the same public release",
        )
    period_count = await session.scalar(
        select(func.count(ClimateObservation.id)).where(
            *observation_filter,
            ClimateObservation.observed_at >= body.period_start,
            ClimateObservation.observed_at <= body.period_end,
        )
    )
    if period_count != observation_count:
        raise HTTPException(422, "The declared release period must include every observation in the source run")
    if not source_run.licence:
        raise HTTPException(422, "The source ingestion run has no recorded provider licence")
    dimensions = (
        await session.execute(
            select(ClimateObservation.variable, ClimateObservation.unit)
            .where(*observation_filter)
            .group_by(ClimateObservation.variable, ClimateObservation.unit)
        )
    ).all()
    if len(dimensions) != 1:
        raise HTTPException(422, "A public release must contain one climate variable and unit")
    variable, unit = dimensions[0]
    grouped = (
        await session.execute(
            select(
                ClimateObservation.observed_at,
                func.avg(ClimateObservation.value),
            )
            .where(
                *observation_filter,
                ClimateObservation.quality_status == "verified",
                ClimateObservation.observed_at >= body.period_start,
                ClimateObservation.observed_at <= body.period_end,
            )
            .group_by(ClimateObservation.observed_at)
            .order_by(ClimateObservation.observed_at)
            .limit(5001)
        )
    ).all()
    if not grouped or len(grouped) > 5000:
        raise HTTPException(
            422,
            "The release period must contain between 1 and 5000 distinct observation timestamps",
        )
    series_json: list[dict[str, object]] = []
    for observed_at, mean_value in grouped:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        series_json.append({
            "observed_at": observed_at.isoformat(),
            "value": float(mean_value),
        })
    latest = await session.scalar(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == organization_id,
        ClimatePublicRelease.slug == body.slug,
    ).order_by(ClimatePublicRelease.version.desc()).limit(1))
    if latest is not None and latest.state not in {"published", "retracted"}:
        raise HTTPException(409, "An existing release version is still in workflow")
    next_version = latest.version + 1 if latest is not None else 1
    row = ClimatePublicRelease(
        organization_id=organization_id,
        slug=body.slug,
        version=next_version,
        title=body.title.strip(),
        summary=body.summary.strip(),
        state="draft",
        indicator=variable,
        unit=unit,
        provider_id=body.provider_id,
        provider_product=f"{source_run.source_name} {str(product_variant).upper()}",
        provider_version="3.0",
        data_class=expected_data_class,
        geography_label=area_label,
        geography_resolution="0.05° CHIRPS grid; arithmetic mean per day",
        period_start=body.period_start.astimezone(UTC),
        period_end=body.period_end.astimezone(UTC),
        baseline=body.baseline,
        aggregation_method="Arithmetic mean of independently verified provider observations at each timestamp; no imputation.",
        coverage_pct=None,
        missingness_pct=None,
        uncertainty_summary=body.uncertainty_summary,
        limitations=body.limitations,
        license_name=source_run.licence,
        attribution=f"Climate Hazards Center (CHC), {source_run.source_name} {str(product_variant).upper()}.",
        terms_url="https://www.chc.ucsb.edu/data/chirps",
        citation_url="https://doi.org/10.15780/G2JQ0P",
        source_ingestion_run_id=body.source_ingestion_run_id,
        series_json=series_json,
        regions_json=[],
        created_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    _event(session, row, principal.user_id, "created", None, "draft")
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row)


@router.get(
    "/organizations/{organization_id}/climate-public-releases",
    response_model=list[ClimateReleaseWorkspaceRead],
)
async def list_organisation_releases(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ClimateReleaseWorkspaceRead]:
    """List release workflow records visible to authorised research workspace members."""
    if not await membership_has_any_role(session, membership, _RELEASE_ROLES | _REVIEW_ROLES):
        raise HTTPException(403, "Climate release workspace access is not permitted")
    rows = list((await session.scalars(
        select(ClimatePublicRelease)
        .where(ClimatePublicRelease.organization_id == organization_id)
        .order_by(ClimatePublicRelease.created_at.desc())
        .limit(limit)
    )).all())
    if not rows:
        return []
    events = await session.scalars(
        select(ClimatePublicReleaseEvent)
        .where(
            ClimatePublicReleaseEvent.release_id.in_([row.id for row in rows]),
            ClimatePublicReleaseEvent.action == "licence_reviewed",
        )
        .order_by(ClimatePublicReleaseEvent.created_at.desc())
    )
    latest_reviews: dict[str, ClimatePublicReleaseEvent] = {}
    for event in events.all():
        latest_reviews.setdefault(event.release_id, event)
    return [_workspace_read(row, latest_reviews.get(row.id)) for row in rows]


async def _get_release(
    session: AsyncSession, organization_id: str, release_id: str
) -> ClimatePublicRelease:
    row = await session.scalar(select(ClimatePublicRelease).where(
        ClimatePublicRelease.id == release_id,
        ClimatePublicRelease.organization_id == organization_id,
    ))
    if row is None:
        raise HTTPException(404, "Climate release not found")
    return row


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/submit",
    response_model=ClimateReleaseWorkspaceRead,
)
async def submit_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    row = await _get_release(session, organization_id, release_id)
    if row.created_by != principal.user_id and not await membership_has_any_role(
        session, membership, _REVIEW_ROLES
    ):
        raise HTTPException(404, "Climate release not found")
    if row.state != "draft":
        raise HTTPException(409, "Only draft releases can be submitted")
    row.state = "review"
    _event(session, row, principal.user_id, "submitted", "draft", "review", body.note)
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/licence-review",
    response_model=ClimateReleaseWorkspaceRead,
)
async def review_release_licence(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseLicenceReview,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate licence reviewer role required")
    row = await _get_release(session, organization_id, release_id)
    if row.state != "review":
        raise HTTPException(409, "Only submitted releases can receive a licence review")
    if row.created_by == principal.user_id:
        raise HTTPException(403, "A release author cannot review their own licence")
    if not all((row.license_name, row.terms_url, row.attribution, row.citation_url)):
        raise HTTPException(422, "Licence, provider terms, attribution and citation must be present")
    source_run = await _release_source_run(session, row)
    quality_reviewers = await _quality_reviewers(session, row)
    if principal.user_id in quality_reviewers or principal.user_id == source_run.started_by:
        raise HTTPException(
            403,
            "Licence review must be independent of the ingestion operator and quality reviewer",
        )
    if await _latest_licence_review(session, row.id) is not None:
        raise HTTPException(409, "A licence review is already recorded for this release version")

    review_note = json.dumps(
        {
            "checks": {
                "licence_terms": body.licence_terms_confirmed,
                "provider_terms": body.provider_terms_confirmed,
                "attribution": body.attribution_confirmed,
                "citation": body.citation_confirmed,
            },
            "licence_name": row.license_name,
            "terms_url": row.terms_url,
            "attribution_text": row.attribution,
            "citation_url": row.citation_url,
            "review_note": body.note.strip(),
        },
        sort_keys=True,
    )
    event = _event(
        session, row, principal.user_id, "licence_reviewed", "review", "review", review_note
    )
    await session.commit()
    await session.refresh(row)
    await session.refresh(event)
    return _workspace_read(row, event)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/approve",
    response_model=ClimateReleaseWorkspaceRead,
)
async def approve_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate release reviewer role required")
    row = await _get_release(session, organization_id, release_id)
    if row.created_by == principal.user_id:
        raise HTTPException(403, "A release author cannot approve their own release")
    if row.state != "review":
        raise HTTPException(409, "Only submitted releases can be approved")
    if body.note is None or len(body.note.strip()) < 10:
        raise HTTPException(422, "A substantive independent approval note is required")
    licence_event = await _latest_licence_review(session, row.id)
    if licence_event is None or not _licence_review_is_complete(licence_event):
        raise HTTPException(409, "An independent licence and attribution review is required before approval")
    if licence_event.actor_user_id == principal.user_id:
        raise HTTPException(403, "The licence reviewer cannot approve the same release")
    source_run = await _release_source_run(session, row)
    quality_reviewers = await _quality_reviewers(session, row)
    if principal.user_id in quality_reviewers or principal.user_id == source_run.started_by:
        raise HTTPException(403, "A quality reviewer or ingestion operator cannot approve the release")
    row.state = "approved"
    row.reviewed_by = principal.user_id
    row.approved_at = datetime.now(UTC)
    _event(session, row, principal.user_id, "approved", "review", "approved", body.note)
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row, licence_event)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/publish",
    response_model=ClimateReleaseWorkspaceRead,
)
async def publish_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate release publisher role required")
    row = await _get_release(session, organization_id, release_id)
    if row.state != "approved" or row.approved_at is None or row.reviewed_by is None:
        raise HTTPException(409, "Release must be independently approved before publication")
    if body.note is None or len(body.note.strip()) < 10:
        raise HTTPException(422, "A substantive publication decision note is required")
    licence_event = await _latest_licence_review(session, row.id)
    if licence_event is None or not _licence_review_is_complete(licence_event):
        raise HTTPException(409, "The independent licence review is missing")
    source_run = await _release_source_run(session, row)
    quality_reviewers = await _quality_reviewers(session, row)
    restricted_actors = {
        row.created_by,
        source_run.started_by,
        row.reviewed_by,
        licence_event.actor_user_id,
        *quality_reviewers,
    }
    if principal.user_id in restricted_actors:
        raise HTTPException(
            403,
            "Publication must be performed by someone independent of authorship, quality, licence and release review",
        )
    previous_versions = await session.scalars(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == organization_id,
        ClimatePublicRelease.slug == row.slug,
        ClimatePublicRelease.state == "published",
        ClimatePublicRelease.id != row.id,
    ))
    for previous in previous_versions.all():
        previous.state = "superseded"
        _event(
            session,
            previous,
            principal.user_id,
            "superseded",
            "published",
            "superseded",
            f"Superseded by version {row.version}",
        )
    row.state = "published"
    row.published_by = principal.user_id
    row.published_at = datetime.now(UTC)
    _event(session, row, principal.user_id, "published", "approved", "published", body.note)
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row, licence_event)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/retract",
    response_model=ClimateReleaseWorkspaceRead,
)
async def retract_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseWorkspaceRead:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate release publisher role required")
    if body.note is None or len(body.note.strip()) < 5:
        raise HTTPException(422, "A substantive retraction reason is required")
    row = await _get_release(session, organization_id, release_id)
    if row.state != "published":
        raise HTTPException(409, "Only published releases can be retracted")
    row.state = "retracted"
    row.retracted_at = datetime.now(UTC)
    row.retraction_reason = body.note.strip()
    _event(session, row, principal.user_id, "retracted", "published", "retracted", body.note)
    await session.commit()
    await session.refresh(row)
    licence_event = await _latest_licence_review(session, row.id)
    return _workspace_read(row, licence_event)


@router.get(
    "/public/organizations/{organization_slug}/climate/releases",
    response_model=list[ClimateReleaseSummary],
)
async def list_public_releases(
    organization_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    indicator: str | None = Query(default=None, min_length=2, max_length=100),
    data_class: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ClimateReleaseSummary] | Response:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    statement = select(ClimatePublicRelease).where(*_public_release_filters(org.id, request.app.state.settings))
    if indicator:
        statement = statement.where(ClimatePublicRelease.indicator == indicator)
    if data_class:
        if data_class not in _DATA_CLASSES:
            raise HTTPException(422, "Unsupported climate data class")
        statement = statement.where(ClimatePublicRelease.data_class == data_class)
    rows = await session.scalars(
        statement.order_by(ClimatePublicRelease.published_at.desc()).limit(limit)
    )
    result = [_summary(row) for row in rows.all()]
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result


@router.get(
    "/public/organizations/{organization_slug}/climate/releases/{release_slug}",
    response_model=ClimateReleaseDetail,
)
async def get_public_release(
    organization_slug: str,
    release_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail | Response:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Climate release not found")
    row = await session.scalar(select(ClimatePublicRelease).where(
        *_public_release_filters(org.id, request.app.state.settings),
        ClimatePublicRelease.slug == release_slug,
    ).order_by(ClimatePublicRelease.version.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "Climate release not found")
    result = ClimateReleaseDetail.model_validate(row)
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result


@router.get(
    "/public/organizations/{organization_slug}/climate/releases/{release_slug}/series",
    response_model=ClimateReleaseSeries,
)
async def get_public_release_series(
    organization_slug: str,
    release_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseSeries | Response:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Climate release not found")
    row = await session.scalar(select(ClimatePublicRelease).where(
        *_public_release_filters(org.id, request.app.state.settings),
        ClimatePublicRelease.slug == release_slug,
    ).order_by(ClimatePublicRelease.version.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "Climate release not found")
    result = ClimateReleaseSeries(
        release=ClimateReleaseDetail.model_validate(row),
        series=[ClimateSeriesPoint.model_validate(point) for point in row.series_json],
        regions=[ClimateRegionValue.model_validate(region) for region in row.regions_json],
    )
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result


@router.get(
    "/public/organizations/{organization_slug}/climate/overview",
    response_model=dict[str, object],
)
async def public_climate_overview(
    organization_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object] | Response:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    public_filters = _public_release_filters(org.id, request.app.state.settings)
    release_stats = await session.execute(
        select(
            func.count(ClimatePublicRelease.id),
            func.max(ClimatePublicRelease.published_at),
            func.max(ClimatePublicRelease.period_end),
        ).where(*public_filters)
    )
    release_count, latest_published_at, latest_data_period_end = release_stats.one()
    indicators = await session.scalars(
        select(ClimatePublicRelease.indicator).where(*public_filters).distinct()
    )
    latest_source_retrieved_at = await session.scalar(
        select(func.max(ClimateIngestionRun.finished_at))
        .join(
            ClimatePublicRelease,
            ClimatePublicRelease.source_ingestion_run_id == ClimateIngestionRun.id,
        )
        .where(
            ClimateIngestionRun.organization_id == org.id,
            ClimatePublicRelease.organization_id == org.id,
            *public_filters,
        )
    )
    result: dict[str, object] = {
        "organization": org.name,
        "release_count": release_count,
        "indicators": sorted(indicators.all()),
        "latest_published_at": latest_published_at.isoformat() if latest_published_at else None,
        "latest_data_period_end": latest_data_period_end.isoformat() if latest_data_period_end else None,
        "latest_source_retrieved_at": (
            latest_source_retrieved_at.isoformat() if latest_source_retrieved_at else None
        ),
    }
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result




@router.get(
    "/public/organizations/{organization_slug}/climate/insights",
    response_model=list[ClimateInsightRead],
)
async def public_climate_insights(
    organization_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ClimateInsightRead] | Response:
    """Return editorial insights only when both linked evidence and publication are public."""
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    entries = await session.scalars(
        select(PublicContentEntry)
        .where(
            PublicContentEntry.organization_id == org.id,
            PublicContentEntry.content_type == "climate_insight",
            PublicContentEntry.publication_state == "published",
        )
        .order_by(PublicContentEntry.published_at.desc(), PublicContentEntry.title)
        .limit(100)
    )
    result: list[ClimateInsightRead] = []
    for entry in entries.all():
        metadata = entry.metadata_json if isinstance(entry.metadata_json, dict) else {}
        release_slug = metadata.get("release_slug")
        publication_slug = metadata.get("publication_slug")
        if (
            not isinstance(release_slug, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", release_slug)
            or not isinstance(publication_slug, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", publication_slug)
        ):
            continue
        release_exists = await session.scalar(
            select(ClimatePublicRelease.id).where(
                *_public_release_filters(org.id, request.app.state.settings),
                ClimatePublicRelease.slug == release_slug,
            ).limit(1)
        )
        publication = await session.scalar(
            select(PublicContentEntry).where(
                PublicContentEntry.organization_id == org.id,
                PublicContentEntry.slug == publication_slug,
                PublicContentEntry.content_type == "publication",
                PublicContentEntry.publication_state == "published",
            )
        )
        if release_exists is None or publication is None:
            continue
        publication_url = (
            publication.source_url
            if isinstance(publication.source_url, str)
            and publication.source_url.startswith("https://")
            else None
        )
        region = metadata.get("region")
        indicator = metadata.get("indicator")
        evidence_note = metadata.get("evidence_note")
        result.append(ClimateInsightRead(
            id=entry.id,
            slug=entry.slug,
            title=entry.title,
            summary=entry.summary,
            body=entry.body,
            region=region if isinstance(region, str) else None,
            indicator=indicator if isinstance(indicator, str) else None,
            evidence_note=evidence_note if isinstance(evidence_note, str) else None,
            release_slug=release_slug,
            publication_title=publication.title,
            publication_url=publication_url,
            published_at=entry.published_at,
        ))
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result


@router.get(
    "/public/organizations/{organization_slug}/climate/sources",
    response_model=list[ClimateSourceRead],
)
async def public_climate_sources(
    organization_slug: str,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ClimateSourceRead] | Response:
    """Return a public-safe catalogue of sources used by published releases."""
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    rows = await session.scalars(select(ClimatePublicRelease).where(
        *_public_release_filters(org.id, request.app.state.settings),
    ).order_by(ClimatePublicRelease.published_at.desc()).limit(100))
    sources: dict[tuple[str, str, str], ClimateSourceRead] = {}
    for row in rows.all():
        key = (row.provider_id, row.provider_product, row.data_class)
        if key not in sources:
            sources[key] = ClimateSourceRead(
                provider_id=row.provider_id,
                provider_product=row.provider_product,
                data_class=row.data_class,
                license_name=row.license_name,
                attribution=row.attribution,
                terms_url=row.terms_url,
                citation_url=row.citation_url,
                release_count=1,
            )
        else:
            source = sources[key]
            sources[key] = source.model_copy(
                update={"release_count": source.release_count + 1}
            )
    result = list(sources.values())
    cached = _public_cache_response(request, response, result)
    if cached is not None:
        return cached
    return result
