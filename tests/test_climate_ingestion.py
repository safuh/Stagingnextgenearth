"""Tests for the provider-neutral climate ingestion contract."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimateMeasurement,
    ClimateProviderRequest,
)


def test_provider_request_accepts_timezone_aware_period_and_wgs84_area() -> None:
    request = ClimateProviderRequest(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
        area=ClimateBoundingBox(west=34.0, south=-5.0, east=42.0, north=5.0),
    )

    assert request.area is not None
    assert request.area.west == 34.0
    assert request.end > request.start


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 1, 1), datetime(2026, 2, 1, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1)),
        (datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_provider_request_rejects_naive_or_reversed_period(
    start: datetime, end: datetime
) -> None:
    with pytest.raises(ValidationError):
        ClimateProviderRequest(start=start, end=end)


@pytest.mark.parametrize(
    "bounds",
    [
        {"west": 42, "south": -5, "east": 34, "north": 5},
        {"west": 34, "south": 5, "east": 42, "north": -5},
        {"west": 34, "south": -5, "east": 181, "north": 5},
    ],
)
def test_bounding_box_rejects_invalid_wgs84_bounds(bounds: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        ClimateBoundingBox(**bounds)


def test_measurement_validates_identity_timezone_and_finite_values() -> None:
    measurement = ClimateMeasurement(
        provider_record_id="power:2026-01-01:rainfall",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        variable="precipitation",
        value=12.5,
        unit="mm",
        latitude=-1.286,
        longitude=36.817,
        metadata={"provider": "NASA POWER", "quality_flag": "validated"},
    )

    assert measurement.provider_record_id == "power:2026-01-01:rainfall"
    assert measurement.value == 12.5
    assert measurement.metadata["provider"] == "NASA POWER"


def test_measurement_rejects_naive_timestamp_and_non_finite_value() -> None:
    with pytest.raises(ValidationError):
        ClimateMeasurement(
            provider_record_id="record-1",
            observed_at=datetime(2026, 1, 1),
            variable="precipitation",
            value=1.0,
            unit="mm",
            latitude=0,
            longitude=0,
        )

    with pytest.raises(ValidationError):
        ClimateMeasurement(
            provider_record_id="record-2",
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            variable="precipitation",
            value=float("nan"),
            unit="mm",
            latitude=0,
            longitude=0,
        )


def test_measurement_rejects_extra_provider_fields_and_invalid_coordinates() -> None:
    with pytest.raises(ValidationError):
        ClimateMeasurement(
            provider_record_id="record-3",
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            variable="precipitation",
            value=1.0,
            unit="mm",
            latitude=91,
            longitude=0,
        )

    with pytest.raises(ValidationError):
        ClimateMeasurement(
            provider_record_id="record-4",
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            variable="precipitation",
            value=1.0,
            unit="mm",
            latitude=0,
            longitude=0,
            unnormalized_payload={"raw": "data"},
        )
