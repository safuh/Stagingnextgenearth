"""Tests for idempotent climate provider persistence and run provenance."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.climate_ingestion import (
    ClimateMeasurement,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.climate_persistence import persist_provider_measurements
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import User
from stagingnextgenearth.platform.models import (
    ClimateIngestionRun,
    ClimateObservation,
    Organization,
)


def _measurement(record_id: str) -> ClimateMeasurement:
    return ClimateMeasurement(
        provider_record_id=record_id,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        variable="precipitation",
        value=18.2,
        unit="mm",
        latitude=-1.286,
        longitude=36.817,
        metadata={"dataset": "daily"},
    )


async def _stream(*items: ClimateMeasurement) -> AsyncIterator[ClimateMeasurement]:
    for item in items:
        yield item


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    user = User(identifier="climate-researcher@example.org", password_hash="test-hash")
    session.add(user)
    await session.flush()
    organization = Organization(
        name="Climate Research",
        slug="climate-research",
        owner_user_id=user.id,
    )
    session.add(organization)
    await session.flush()
    request = ClimateProviderRequest(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
        point=ClimatePoint(latitude=-1.286, longitude=36.817),
    )
    return engine, session, user, organization, request


@pytest.mark.asyncio
async def test_provider_persistence_is_idempotent_and_keeps_records_pending() -> None:
    engine, session, user, organization, request = await _database()
    try:
        first = await persist_provider_measurements(
            session,
            organization_id=organization.id,
            actor_user_id=user.id,
            provider_id="example-climate",
            source_name="Example Climate Archive",
            licence="CC-BY-4.0",
            request=request,
            measurements=_stream(_measurement("record-1"), _measurement("record-2")),
        )
        await session.commit()

        assert first.status == "completed"
        assert first.requested_area == {"point": {"latitude": -1.286, "longitude": 36.817}}
        assert (first.records_received, first.records_inserted, first.records_skipped) == (
            2, 2, 0
        )

        replay = await persist_provider_measurements(
            session,
            organization_id=organization.id,
            actor_user_id=user.id,
            provider_id="example-climate",
            source_name="Example Climate Archive",
            licence="CC-BY-4.0",
            request=request,
            measurements=_stream(_measurement("record-1")),
        )
        await session.commit()

        assert replay.records_received == 1
        assert replay.records_inserted == 0
        assert replay.records_skipped == 1
        observations = list((await session.scalars(select(ClimateObservation))).all())
        assert len(observations) == 2
        assert all(item.quality_status == "pending" for item in observations)
        assert all(item.provider_id == "example-climate" for item in observations)
        assert all(item.ingestion_run_id == first.id for item in observations)
        runs = list((await session.scalars(select(ClimateIngestionRun))).all())
        assert len(runs) == 2
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_failed_provider_stream_rolls_back_partial_observations() -> None:
    engine, session, user, organization, request = await _database()

    async def failing_stream() -> AsyncIterator[ClimateMeasurement]:
        yield _measurement("partial-record")
        raise RuntimeError("upstream failure details must not be stored")

    try:
        with pytest.raises(RuntimeError, match="upstream failure"):
            await persist_provider_measurements(
                session,
                organization_id=organization.id,
                actor_user_id=user.id,
                provider_id="example-climate",
                source_name="Example Climate Archive",
                licence="CC-BY-4.0",
                request=request,
                measurements=failing_stream(),
            )

        # A caller may commit the audit row after handling the provider error.
        await session.commit()
        observations = list((await session.scalars(select(ClimateObservation))).all())
        runs = list((await session.scalars(select(ClimateIngestionRun))).all())
        assert observations == []
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert runs[0].records_received == 1
        assert runs[0].records_inserted == 0
        assert "upstream failure details" not in (runs[0].error_summary or "")
    finally:
        await session.close()
        await engine.dispose()
