"""Tests for tenant climate-ingestion orchestration request validation."""

import os
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.api.climate_ingestion import (
    ClimateIngestionCreate,
    _provider_for,
    _provider_ingestion_guard,
)
from stagingnextgenearth.climate_ingestion import ClimateBoundingBox, ClimatePoint


def _period() -> dict[str, datetime]:
    return {
        "start": datetime(2026, 1, 1, tzinfo=UTC),
        "end": datetime(2026, 1, 2, tzinfo=UTC),
    }


def test_ingestion_request_rejects_arbitrary_fields_and_invalid_provider() -> None:
    with pytest.raises(ValueError):
        ClimateIngestionCreate(
            **_period(),
            provider="https://example.invalid",
            point={"latitude": -1.2, "longitude": 36.8},
        )


def test_ingestion_request_requires_timezone_aware_period() -> None:
    with pytest.raises(ValueError):
        ClimateIngestionCreate(
            provider="nasa-power",
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2),
            point={"latitude": -1.2, "longitude": 36.8},
        )


def test_nasa_power_orchestration_requires_point_not_area() -> None:
    body = ClimateIngestionCreate(
        provider="nasa-power",
        **_period(),
        area={"west": 36, "south": -2, "east": 37, "north": -1},
    )
    with pytest.raises(HTTPException) as exc:
        _provider_for(body)
    assert exc.value.status_code == 422


def test_chirps_orchestration_selects_requested_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import stagingnextgenearth.api.climate_ingestion as api_module

    monkeypatch.setattr(
        api_module,
        "find_spec",
        lambda name: object() if name == "rasterio" else None,
    )
    body = ClimateIngestionCreate(
        provider="chirps-v3",
        chirps_variant="sat",
        **_period(),
        point={"latitude": -1.2, "longitude": 36.8},
    )
    provider = _provider_for(body)
    assert provider.provider_id == "chirps-v3"
    assert provider.variant == "sat"


def test_copernicus_orchestration_is_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    import stagingnextgenearth.api.climate_ingestion as api_module

    monkeypatch.setattr(api_module, "find_spec", lambda _name: object())
    body = ClimateIngestionCreate(
        provider="copernicus-era5",
        **_period(),
        point=ClimatePoint(latitude=-1.2, longitude=36.8),
    )
    provider = _provider_for(body)
    assert provider.provider_id == "copernicus-era5"


def test_ingestion_model_rejects_both_spatial_scopes() -> None:
    with pytest.raises(ValueError):
        ClimateIngestionCreate(
            provider="chirps-v3",
            **_period(),
            point=ClimatePoint(latitude=-1.2, longitude=36.8),
            area=ClimateBoundingBox(west=36, south=-2, east=37, north=-1),
        )



@pytest.mark.integration
@pytest.mark.asyncio
async def test_chirps_ingestion_guard_serializes_postgres_sessions() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for the PostgreSQL lock test")

    engine = create_async_engine(database_url)
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("The CHIRPS advisory lock is PostgreSQL-specific")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as first, factory() as second:
            async with _provider_ingestion_guard(first, "chirps-v3"):
                with pytest.raises(HTTPException) as exc:
                    async with _provider_ingestion_guard(second, "chirps-v3"):
                        pytest.fail("a second CHIRPS ingestion acquired the active lock")
                assert exc.value.status_code == 409
                await first.commit()

            await second.rollback()
            async with _provider_ingestion_guard(second, "chirps-v3"):
                await second.commit()
    finally:
        await engine.dispose()
