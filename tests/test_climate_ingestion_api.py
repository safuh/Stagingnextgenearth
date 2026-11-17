"""Tests for tenant climate-ingestion orchestration request validation."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from stagingnextgenearth.api.climate_ingestion import (
    ClimateIngestionCreate,
    _provider_for,
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


def test_chirps_orchestration_selects_requested_variant() -> None:
    body = ClimateIngestionCreate(
        provider="chirps-v3",
        chirps_variant="sat",
        **_period(),
        point={"latitude": -1.2, "longitude": 36.8},
    )
    provider = _provider_for(body)
    assert provider.provider_id == "chirps-v3"
    assert provider.variant == "sat"


def test_copernicus_orchestration_is_allowlisted() -> None:
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
