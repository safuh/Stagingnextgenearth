"""Tests for idempotent climate provider persistence and run provenance."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
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
from stagingnextgenearth.providers import chirps
from stagingnextgenearth.providers.chirps import CHIRPSProvider


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
        assert observations[0].unit == "mm/day"
        assert observations[0].metadata_json["normalization"] == {
            "source_value": 18.2,
            "source_unit": "mm",
            "canonical_value": 18.2,
            "canonical_unit": "mm/day",
            "conversion": "mm to mm/day daily accumulation",
        }
        assert observations[0].metadata_json["quality_screening_flags"] == []
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


@pytest.mark.asyncio
async def test_chirps_provider_stream_persists_with_provider_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session, user, organization, _ = await _database()
    monkeypatch.setattr(
        chirps,
        "_decode_geotiff",
        lambda content, point, area, max_cells: [(-1.25, 36.75, 7.4)],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"mock-geotiff")

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = CHIRPSProvider(client=client, variant="rnl")
            request = ClimateProviderRequest(
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 1, 2, tzinfo=UTC),
                area=ClimateBoundingBox(
                    west=36.7, south=-1.3, east=36.8, north=-1.2
                ),
            )
            run = await persist_provider_measurements(
                session,
                organization_id=organization.id,
                actor_user_id=user.id,
                provider_id=provider.provider_id,
                source_name=provider.source_name,
                licence=provider.licence,
                request=request,
                measurements=provider.fetch(request),
            )

        await session.commit()
        observations = list(
            (await session.scalars(select(ClimateObservation))).all()
        )
        assert run.status == "completed"
        assert run.records_received == 1
        assert run.records_inserted == 1
        assert len(observations) == 1
        observation = observations[0]
        assert observation.provider_id == "chirps-v3"
        assert observation.provider_record_id == "rnl:2026-01-01:-1.25000:36.75000"
        assert observation.source == "CHIRPS v3"
        assert observation.unit == "mm/day"
        assert observation.quality_status == "pending"
        assert observation.metadata_json["provider_variant"] == "rnl"
        assert observation.metadata_json["provider_licence"] == "CC-BY-4.0"
        assert observation.ingestion_run_id == run.id
    finally:
        await session.close()
        await engine.dispose()
