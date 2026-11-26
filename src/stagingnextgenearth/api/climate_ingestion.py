"""Trusted, tenant-scoped climate provider ingestion endpoint."""

from datetime import UTC, datetime
from importlib.util import find_spec
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.climate_persistence import persist_provider_measurements
from stagingnextgenearth.platform.models import (
    ClimateIngestionRun,
    ClimateObservation,
    Membership,
    OrganizationAuditEvent,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-ingestion",
    tags=["climate-ingestion"],
)
_INGEST_ROLES = {"admin", "founder", "executive", "researcher"}


class ClimateIngestionCreate(BaseModel):
    """A bounded provider retrieval request; never accepts arbitrary source URLs."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["nasa-power", "chirps-v3", "copernicus-era5"]
    start: datetime
    end: datetime
    point: ClimatePoint | None = None
    area: ClimateBoundingBox | None = None
    area_label: str | None = Field(default=None, min_length=2, max_length=200)
    chirps_variant: Literal["rnl", "sat"] = "rnl"

    @model_validator(mode="after")
    def validate_request_bounds(self) -> "ClimateIngestionCreate":
        for name, value in (("start", self.start), ("end", self.end)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        if (self.point is None) == (self.area is None):
            raise ValueError("specify exactly one point or bounding box")
        return self


class ClimateIngestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_id: str
    source_name: str
    status: str
    records_received: int
    records_inserted: int
    records_skipped: int
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    requested_start: datetime
    requested_end: datetime
    requested_area: dict[str, object] | None = None
    licence: str | None = None
    pending_observations: int = 0
    verified_observations: int = 0
    rejected_observations: int = 0


@router.get("", response_model=list[ClimateIngestionRead])
async def list_climate_ingestion_runs(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ClimateIngestionRead]:
    """List recent provider runs within the caller's organisation."""
    if not await membership_has_any_role(
        session, membership, _INGEST_ROLES | {"executive", "founder", "programme_manager"}
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Climate ingestion access is not permitted")
    rows = await session.scalars(
        select(ClimateIngestionRun)
        .where(ClimateIngestionRun.organization_id == organization_id)
        .order_by(ClimateIngestionRun.started_at.desc())
        .limit(limit)
    )
    runs = rows.all()
    if not runs:
        return []
    counts = (
        await session.execute(
            select(
                ClimateObservation.ingestion_run_id,
                ClimateObservation.quality_status,
                func.count(ClimateObservation.id),
            )
            .where(
                ClimateObservation.organization_id == organization_id,
                ClimateObservation.ingestion_run_id.in_([run.id for run in runs]),
            )
            .group_by(
                ClimateObservation.ingestion_run_id,
                ClimateObservation.quality_status,
            )
        )
    ).all()
    quality_by_run: dict[str, dict[str, int]] = {}
    for run_id, quality_status, count in counts:
        quality_by_run.setdefault(str(run_id), {})[str(quality_status)] = int(count)
    result: list[ClimateIngestionRead] = []
    for run in runs:
        quality = quality_by_run.get(run.id, {})
        result.append(
            ClimateIngestionRead.model_validate(run).model_copy(
                update={
                    "pending_observations": quality.get("pending", 0),
                    "verified_observations": quality.get("verified", 0),
                    "rejected_observations": quality.get("rejected", 0),
                }
            )
        )
    return result


class ClimateIngestionReview(BaseModel):
    decision: Literal["verified", "rejected"]
    note: str = Field(min_length=5, max_length=2000)


class ClimateIngestionReviewResult(BaseModel):
    ingestion_run_id: str
    reviewed_count: int
    decision: Literal["verified", "rejected"]


@router.post("/{run_id}/review", response_model=ClimateIngestionReviewResult)
async def review_climate_ingestion_run(
    organization_id: str,
    run_id: str,
    body: ClimateIngestionReview,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateIngestionReviewResult:
    """Apply one independent quality decision to all pending records in a provider run."""
    if not await membership_has_any_role(session, membership, {"admin", "programme_manager"}):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Climate quality reviewer role required",
        )
    run = await session.scalar(
        select(ClimateIngestionRun).where(
            ClimateIngestionRun.id == run_id,
            ClimateIngestionRun.organization_id == organization_id,
            ClimateIngestionRun.status == "completed",
        )
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Completed provider run not found")
    observations = await session.scalars(
        select(ClimateObservation).where(
            ClimateObservation.organization_id == organization_id,
            ClimateObservation.ingestion_run_id == run_id,
            ClimateObservation.quality_status == "pending",
        )
    )
    pending = observations.all()
    if not pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This provider run has no pending observations"
        )
    if any(item.created_by == principal.user_id for item in pending):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A submitter cannot quality-review their own provider observations",
        )
    now = datetime.now(UTC)
    for item in pending:
        item.quality_status = body.decision
        item.reviewed_by = principal.user_id
        item.reviewed_at = now
        item.review_note = body.note.strip()
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                subject_user_id=item.created_by,
                action="climate.observation.reviewed",
                changes={
                    "observation_id": item.id,
                    "ingestion_run_id": run_id,
                    "decision": body.decision,
                    "variable": item.variable,
                    "source": item.source,
                    "observed_at": item.observed_at.isoformat(),
                    "note": item.review_note,
                },
            )
        )
    await session.commit()
    return ClimateIngestionReviewResult(
        ingestion_run_id=run_id,
        reviewed_count=len(pending),
        decision=body.decision,
    )


@router.post("", response_model=ClimateIngestionRead, status_code=status.HTTP_200_OK)
async def run_climate_ingestion(
    organization_id: str,
    body: ClimateIngestionCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateIngestionRead:
    """Run a bounded allow-listed provider job and persist results as pending review."""
    if not await membership_has_any_role(session, membership, _INGEST_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Climate ingestion requires an administrator or researcher role",
        )
    if (body.point is None) == (body.area is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Specify exactly one point or bounding box",
        )
    try:
        request = ClimateProviderRequest(
            start=body.start,
            end=body.end,
            point=body.point,
            area=body.area,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    provider = _provider_for(body)
    if provider is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The selected climate provider is not enabled on this deployment",
        )

    try:
        run = await persist_provider_measurements(
            session,
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            provider_id=provider.provider_id,
            source_name=provider.source_name,
            licence=provider.licence,
            request=request,
            measurements=provider.fetch(request),
            area_label=body.area_label,
            product_variant=body.chirps_variant if body.provider == "chirps-v3" else None,
        )
    except Exception as exc:
        # Persistence records a failed run and rolls back partial observations.
        # Commit that audit row when the database transaction remains usable.
        try:
            await session.commit()
        except Exception:
            await session.rollback()
        # Do not return upstream exception text, URLs or credentials to clients.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Climate provider ingestion failed; consult the ingestion run audit record",
        ) from exc
    await session.commit()
    await session.refresh(run)
    return ClimateIngestionRead.model_validate(run)


def _provider_for(body: ClimateIngestionCreate):
    if body.provider == "nasa-power":
        if body.point is None or body.area is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "NASA POWER requires a point location",
            )
        from stagingnextgenearth.providers.nasa_power import NASAPowerProvider

        return NASAPowerProvider()
    if body.provider == "chirps-v3":
        if find_spec("rasterio") is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CHIRPS area ingestion requires the rasterio runtime dependency",
            )
        from stagingnextgenearth.providers.chirps import CHIRPSProvider

        return CHIRPSProvider(variant=body.chirps_variant)
    if any(find_spec(name) is None for name in ("cdsapi", "xarray", "netCDF4")):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Copernicus provider dependencies are not installed",
        )
    from stagingnextgenearth.providers.copernicus import CopernicusERA5Provider

    return CopernicusERA5Provider()
