# ruff: noqa: E501, I001
"""Governed public climate release lifecycle and anonymous read API."""

from datetime import UTC, datetime
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.climate_public import (
    ClimatePublicRelease,
    ClimatePublicReleaseEvent,
)
from stagingnextgenearth.platform.models import (
    ClimateIngestionRun,
    ClimateObservation,
    Membership,
    Organization,
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
_REVIEW_ROLES = {"admin", "founder", "executive"}
_DATA_CLASSES = {
    "station_observation", "satellite_estimate", "reanalysis", "forecast", "projection"
}


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
    release: ClimateReleaseSummary
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


class ClimateReleaseAction(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


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
) -> None:
    session.add(ClimatePublicReleaseEvent(
        organization_id=row.organization_id,
        release_id=row.id,
        actor_user_id=actor_id,
        action=action,
        from_state=from_state,
        to_state=to_state,
        note=note,
    ))


@router.post(
    "/organizations/{organization_id}/climate-public-releases",
    response_model=ClimateReleaseDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_release(
    organization_id: str,
    body: ClimateReleaseCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
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
        )
    )
    if observation_count != source_run.records_inserted or verified_count != observation_count:
        raise HTTPException(
            409,
            "Every inserted observation in the provider run must pass independent quality review",
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
        provider_product=source_run.source_name,
        provider_version=None,
        data_class=body.data_class,
        geography_label=body.geography_label,
        geography_resolution=body.geography_resolution,
        period_start=body.period_start.astimezone(UTC),
        period_end=body.period_end.astimezone(UTC),
        baseline=body.baseline,
        aggregation_method="Arithmetic mean of independently verified provider observations at each timestamp; no imputation.",
        coverage_pct=None,
        missingness_pct=None,
        uncertainty_summary=body.uncertainty_summary,
        limitations=body.limitations,
        license_name=source_run.licence,
        attribution=f"{source_run.source_name} ({source_run.provider_id})",
        terms_url=str(body.terms_url) if body.terms_url else None,
        citation_url=str(body.citation_url) if body.citation_url else None,
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
    return ClimateReleaseDetail.model_validate(row)


@router.get(
    "/organizations/{organization_id}/climate-public-releases",
    response_model=list[ClimateReleaseDetail],
)
async def list_organisation_releases(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ClimateReleaseDetail]:
    """List release workflow records visible to authorised research workspace members."""
    if not await membership_has_any_role(session, membership, _RELEASE_ROLES | _REVIEW_ROLES):
        raise HTTPException(403, "Climate release workspace access is not permitted")
    rows = await session.scalars(
        select(ClimatePublicRelease)
        .where(ClimatePublicRelease.organization_id == organization_id)
        .order_by(ClimatePublicRelease.created_at.desc())
        .limit(limit)
    )
    return [ClimateReleaseDetail.model_validate(row) for row in rows.all()]


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
    response_model=ClimateReleaseDetail,
)
async def submit_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
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
    return ClimateReleaseDetail.model_validate(row)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/approve",
    response_model=ClimateReleaseDetail,
)
async def approve_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate release reviewer role required")
    row = await _get_release(session, organization_id, release_id)
    if row.created_by == principal.user_id:
        raise HTTPException(403, "A release author cannot approve their own release")
    if row.state != "review":
        raise HTTPException(409, "Only submitted releases can be approved")
    row.state = "approved"
    row.reviewed_by = principal.user_id
    row.approved_at = datetime.now(UTC)
    _event(session, row, principal.user_id, "approved", "review", "approved", body.note)
    await session.commit()
    await session.refresh(row)
    return ClimateReleaseDetail.model_validate(row)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/publish",
    response_model=ClimateReleaseDetail,
)
async def publish_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(403, "Climate release publisher role required")
    row = await _get_release(session, organization_id, release_id)
    if row.state != "approved" or row.approved_at is None or row.reviewed_by is None:
        raise HTTPException(409, "Release must be independently approved before publication")
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
    return ClimateReleaseDetail.model_validate(row)


@router.post(
    "/organizations/{organization_id}/climate-public-releases/{release_id}/retract",
    response_model=ClimateReleaseDetail,
)
async def retract_release(
    organization_id: str,
    release_id: str,
    body: ClimateReleaseAction,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
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
    return ClimateReleaseDetail.model_validate(row)


@router.get(
    "/public/organizations/{organization_slug}/climate/releases",
    response_model=list[ClimateReleaseSummary],
)
async def list_public_releases(
    organization_slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    indicator: str | None = Query(default=None, min_length=2, max_length=100),
    data_class: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ClimateReleaseSummary]:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    statement = select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == org.id,
        ClimatePublicRelease.state == "published",
    )
    if indicator:
        statement = statement.where(ClimatePublicRelease.indicator == indicator)
    if data_class:
        if data_class not in _DATA_CLASSES:
            raise HTTPException(422, "Unsupported climate data class")
        statement = statement.where(ClimatePublicRelease.data_class == data_class)
    rows = await session.scalars(
        statement.order_by(ClimatePublicRelease.published_at.desc()).limit(limit)
    )
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    return [_summary(row) for row in rows.all()]


@router.get(
    "/public/organizations/{organization_slug}/climate/releases/{release_slug}",
    response_model=ClimateReleaseDetail,
)
async def get_public_release(
    organization_slug: str,
    release_slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseDetail:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Climate release not found")
    row = await session.scalar(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == org.id,
        ClimatePublicRelease.slug == release_slug,
        ClimatePublicRelease.state == "published",
    ).order_by(ClimatePublicRelease.version.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "Climate release not found")
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    return ClimateReleaseDetail.model_validate(row)


@router.get(
    "/public/organizations/{organization_slug}/climate/releases/{release_slug}/series",
    response_model=ClimateReleaseSeries,
)
async def get_public_release_series(
    organization_slug: str,
    release_slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateReleaseSeries:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Climate release not found")
    row = await session.scalar(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == org.id,
        ClimatePublicRelease.slug == release_slug,
        ClimatePublicRelease.state == "published",
    ).order_by(ClimatePublicRelease.version.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "Climate release not found")
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    return ClimateReleaseSeries(
        release=_summary(row),
        series=[ClimateSeriesPoint.model_validate(point) for point in row.series_json],
        regions=[ClimateRegionValue.model_validate(region) for region in row.regions_json],
    )


@router.get(
    "/public/organizations/{organization_slug}/climate/overview",
    response_model=dict[str, object],
)
async def public_climate_overview(
    organization_slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    rows = await session.scalars(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == org.id,
        ClimatePublicRelease.state == "published",
    ).order_by(ClimatePublicRelease.published_at.desc()).limit(100))
    releases = rows.all()
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    return {
        "organization": org.name,
        "release_count": len(releases),
        "indicators": sorted({row.indicator for row in releases}),
        "latest_published_at": releases[0].published_at.isoformat() if releases and releases[0].published_at else None,
    }




@router.get(
    "/public/organizations/{organization_slug}/climate/sources",
    response_model=list[ClimateSourceRead],
)
async def public_climate_sources(
    organization_slug: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ClimateSourceRead]:
    """Return a public-safe catalogue of sources used by published releases."""
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    rows = await session.scalars(select(ClimatePublicRelease).where(
        ClimatePublicRelease.organization_id == org.id,
        ClimatePublicRelease.state == "published",
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
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    return list(sources.values())
