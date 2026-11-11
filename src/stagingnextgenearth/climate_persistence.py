"""Persistence service for provider-normalized climate observations."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_quality import normalize_climate_value
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
    """Persist one provider stream atomically; new records remain pending review.

    The caller owns the outer transaction and must commit the returned run. A
    savepoint keeps partial observations out of the database if the provider
    stream fails, while allowing the caller to commit the failed-run audit row.
    Provider identity is unique per organisation; the database constraint is
    the final concurrency guard, so callers should retry uniqueness races.
    """
    run = ClimateIngestionRun(
        organization_id=organization_id,
        provider_id=provider_id,
        source_name=source_name,
        licence=licence,
        requested_start=request.start,
        requested_end=request.end,
        requested_area=(
            request.area.model_dump()
            if request.area is not None
            else {"point": request.point.model_dump()}
            if request.point is not None
            else None
        ),
        status="running",
        started_by=actor_user_id,
    )
    session.add(run)
    await session.flush()

    received = 0
    inserted = 0
    skipped = 0
    try:
        async with session.begin_nested():
            async for measurement in measurements:
                received += 1
                existing_id = await session.scalar(
                    select(ClimateObservation.id).where(
                        ClimateObservation.organization_id == organization_id,
                        ClimateObservation.provider_id == provider_id,
                        ClimateObservation.provider_record_id == measurement.provider_record_id,
                    )
                )
                if existing_id is not None:
                    skipped += 1
                    continue

                screened = normalize_climate_value(
                    variable=measurement.variable,
                    value=measurement.value,
                    unit=measurement.unit,
                )
                metadata = {
                    **measurement.metadata,
                    "provider_licence": licence,
                    "normalization": {
                        "source_value": screened.source_value,
                        "source_unit": screened.source_unit,
                        "canonical_value": screened.value,
                        "canonical_unit": screened.unit,
                        "conversion": screened.conversion,
                    },
                    "quality_screening_flags": list(screened.flags),
                }
                session.add(
                    ClimateObservation(
                        organization_id=organization_id,
                        observed_at=measurement.observed_at,
                        variable=screened.variable,
                        value=screened.value,
                        unit=screened.unit,
                        latitude=measurement.latitude,
                        longitude=measurement.longitude,
                        source=source_name,
                        ingestion_run_id=run.id,
                        provider_id=provider_id,
                        provider_record_id=measurement.provider_record_id,
                        quality_status="pending",
                        metadata_json=metadata,
                        created_by=actor_user_id,
                    )
                )
                inserted += 1

            run.records_received = received
            run.records_inserted = inserted
            run.records_skipped = skipped
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            await session.flush()
    except Exception as exc:
        # The savepoint has rolled back all observations from this stream.
        run.records_received = received
        run.records_inserted = 0
        run.records_skipped = skipped
        run.status = "failed"
        run.error_summary = f"{type(exc).__name__}: climate provider stream failed"[:2000]
        run.finished_at = datetime.now(UTC)
        await session.flush()
        raise

    return run
