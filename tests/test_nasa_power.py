"""Tests for the NASA POWER daily point adapter."""

from datetime import UTC, datetime

import httpx
import pytest

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.providers.nasa_power import (
    NASA_POWER_DAILY_POINT_URL,
    NASAPowerProvider,
)


def _payload() -> dict[str, object]:
    return {
        "header": {"title": "NASA/POWER daily data"},
        "messages": [],
        "parameters": {
            "PRECTOTCORR": {"units": "mm/day", "longname": "Precipitation corrected"},
            "T2M": {"units": "C", "longname": "Temperature at 2 Meters"},
        },
        "properties": {
            "parameter": {
                "PRECTOTCORR": {
                    "20260101": 4.2,
                    "20260102": -999.0,
                    "20260103": 0.0,
                },
                "T2M": {"20260101": 24.5, "20260102": 24.8, "20260103": 25.0},
            }
        },
        "geometry": {"type": "Point", "coordinates": [36.817, -1.286, 1600]},
    }


@pytest.mark.asyncio
async def test_nasa_power_normalizes_daily_series_and_omits_missing_values() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json=_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NASAPowerProvider(client=client)
        request = ClimateProviderRequest(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 4, tzinfo=UTC),
            point=ClimatePoint(latitude=-1.286, longitude=36.817),
        )
        measurements = [item async for item in provider.fetch(request)]

    assert captured == {
        "parameters": "PRECTOTCORR,T2M",
        "community": "AG",
        "longitude": "36.817",
        "latitude": "-1.286",
        "start": "20260101",
        "end": "20260103",
        "time-standard": "UTC",
        "format": "JSON",
    }
    assert len(measurements) == 5
    precipitation = [item for item in measurements if item.variable == "precipitation"]
    assert len(precipitation) == 2
    assert precipitation[0].value == 4.2
    assert precipitation[0].unit == "mm/day"
    assert precipitation[0].observed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert precipitation[0].latitude == -1.286
    assert precipitation[0].longitude == 36.817
    assert precipitation[0].metadata["time_standard"] == "UTC"
    assert any(item.variable == "air_temperature_2m" for item in measurements)


@pytest.mark.asyncio
async def test_nasa_power_requires_a_point_and_rejects_area_requests() -> None:
    provider = NASAPowerProvider()
    request = ClimateProviderRequest(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        area=ClimateBoundingBox(west=34, south=-5, east=42, north=5),
    )
    with pytest.raises(ValueError, match="require request.point"):
        await anext(provider.fetch(request))


@pytest.mark.asyncio
async def test_nasa_power_raises_for_unexpected_payload_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"messages": [], "properties": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NASAPowerProvider(client=client)
        request = ClimateProviderRequest(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
            point=ClimatePoint(latitude=-1.286, longitude=36.817),
        )
        with pytest.raises(ValueError, match="missing daily parameter values"):
            await anext(provider.fetch(request))


def test_nasa_power_rejects_more_than_twenty_parameters() -> None:
    with pytest.raises(ValueError, match="at most 20"):
        NASAPowerProvider(parameter_variables={f"P{i}": f"variable_{i}" for i in range(21)})


def test_nasa_power_uses_official_daily_point_endpoint() -> None:
    assert NASA_POWER_DAILY_POINT_URL.endswith("/daily/point")
