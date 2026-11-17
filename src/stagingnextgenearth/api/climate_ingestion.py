"""Trusted, tenant-scoped climate provider ingestion endpoint."""

from datetime import datetime
from importlib.util import find_spec
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.climate_persistence import persist_provider_measurements
from stagingnextgenearth.platform.models import Membership
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
_INGEST_ROLES = {"admin", "researcher"}


class ClimateIngestionCreate(BaseModel):
    """A bounded provider retrieval request; never accepts arbitrary source URLs."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["nasa-power", "chirps-v3", "copernicus-era5"]
    start: datetime
    end: datetime
    point: ClimatePoint | None = None
    area: ClimateBoundingBox | None = None
    chirps_variant: Literal["rnl", "sat"] = "rnl"


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
        from stagingnextgenearth.providers.chirps import CHIRPSProvider

        return CHIRPSProvider(variant=body.chirps_variant)
    if any(find_spec(name) is None for name in ("cdsapi", "xarray", "netCDF4")):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Copernicus provider dependencies are not installed",
        )
    from stagingnextgenearth.providers.copernicus import CopernicusERA5Provider

    return CopernicusERA5Provider()
