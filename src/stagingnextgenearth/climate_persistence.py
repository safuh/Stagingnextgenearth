"""Persistence service for provider-normalized climate observations."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_ingestion import (
    ClimateMeasurement,
    ClimateProviderRequest,
)
from stagingnextgenearth.platform.models import ClimateIngestionRun, ClimateObservation


async def persist_provider_measurements(
    session: AsyncSession,
    *,
    organization_id: str,
    actor_user_id: str,
    provider_id: str,
    source_name: str,
    licence: str | None,
    request: ClimateProviderRequest,
    measurements: AsyncIterator[ClimateMeasurement],
) -> ClimateIngestionRun:
    """Persist one provider stream idempotently; new records remain pending review.

    The caller owns the transaction and must commit the returned run. Provider
    identity is unique per organisation, so replaying a later run cannot create
    duplicate observations. The database constraint is the final concurrency
    guard; callers should retry a transaction after a concurrent uniqueness race.
    """
    run = ClimateIngestionRun(
        organization_id=organization_id,
        provider_id=provider_id,
        source_name=source_name,
        licence=licence,
        requested_start=request.start,
        requested_end=request.end,
        requested_area=request.area.model_dump() if request.area is not None else None,
        status="running",
        started_by=actor_user_id,
    )
    session.add(run)
    await session.flush()

    try:
        async for measurement in measurements:
            run.records_received += 1
            existing_id = await session.scalar(
                select(ClimateObservation.id).where(
                    ClimateObservation.organization_id == organization_id,
                    ClimateObservation.provider_id == provider_id,
                    ClimateObservation.provider_record_id == measurement.provider_record_id,
                )
            )
            if existing_id is not None:
                run.records_skipped += 1
                continue

            session.add(
                ClimateObservation(
                    organization_id=organization_id,
                    observed_at=measurement.observed_at,
                    variable=measurement.variable,
                    value=measurement.value,
                    unit=measurement.unit,
                    latitude=measurement.latitude,
                    longitude=measurement.longitude,
                    source=source_name,
                    ingestion_run_id=run.id,
                    provider_id=provider_id,
                    provider_record_id=measurement.provider_record_id,
                    quality_status="pending",
                    metadata_json={
                        **measurement.metadata,
                        "provider_licence": licence,
                    },
                    created_by=actor_user_id,
                )
            )
            run.records_inserted += 1

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        await session.flush()
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_summary = f"{type(exc).__name__}: climate provider stream failed"[:2000]
        run.finished_at = datetime.now(UTC)
        await session.flush()
        raise
