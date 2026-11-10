"""Tests for the CHIRPS v3 daily raster adapter."""

from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.providers import chirps
from stagingnextgenearth.providers.chirps import (
    CHIRPS_V3_DAILY_BASE_URL,
    CHIRPSProvider,
)


def _request(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    point: ClimatePoint | None = None,
    area: ClimateBoundingBox | None = None,
) -> ClimateProviderRequest:
    return ClimateProviderRequest(
        start=start or datetime(2026, 1, 1, tzinfo=UTC),
        end=end or datetime(2026, 1, 2, tzinfo=UTC),
        point=point,
        area=area,
    )


@pytest.mark.asyncio
async def test_chirps_downloads_official_v3_daily_geotiff_and_normalizes_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, content=b"test-geotiff")

    monkeypatch.setattr(
        chirps,
        "_decode_geotiff",
        lambda content, point, area, max_cells: [(-1.25, 36.75, 12.5)],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CHIRPSProvider(client=client)
        values = [
            item
            async for item in provider.fetch(
                _request(point=ClimatePoint(latitude=-1.26, longitude=36.76))
            )
        ]

    assert captured == [
        f"{CHIRPS_V3_DAILY_BASE_URL}/rnl/2026/chirps-v3.0.rnl.2026.01.01.tif"
    ]
    assert len(values) == 1
    item = values[0]
    assert item.provider_record_id == "rnl:2026-01-01:-1.25000:36.75000"
    assert item.variable == "precipitation"
    assert item.value == 12.5
    assert item.unit == "mm/day"
    assert item.observed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert item.metadata["provider_variant"] == "rnl"
    assert item.metadata["licence"] == "CC-BY-4.0"
    assert item.metadata["spatial_extraction"] == "containing_pixel"


@pytest.mark.asyncio
async def test_chirps_area_request_emits_each_selected_grid_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chirps,
        "_decode_geotiff",
        lambda content, point, area, max_cells: [
            (-1.25, 36.75, 4.0),
            (-1.25, 36.80, 6.0),
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"test-geotiff")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CHIRPSProvider(client=client, variant="sat")
        values = [
            item
            async for item in provider.fetch(
                _request(
                    area=ClimateBoundingBox(
                        west=36.7, south=-1.3, east=36.9, north=-1.2
                    )
                )
            )
        ]

    assert [item.value for item in values] == [4.0, 6.0]
    assert {item.metadata["provider_variant"] for item in values} == {"sat"}
    assert {item.metadata["spatial_extraction"] for item in values} == {
        "cell_centres_in_bbox"
    }


@pytest.mark.asyncio
async def test_chirps_omits_nodata_and_respects_exclusive_end_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, content=b"test-geotiff")

    monkeypatch.setattr(
        chirps,
        "_decode_geotiff",
        lambda content, point, area, max_cells: [
            (-1.25, 36.75, -9999.0),
            (-1.25, 36.75, 0.0),
        ],
    )
    local_zone = timezone(timedelta(hours=3))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CHIRPSProvider(client=client)
        values = [
            item
            async for item in provider.fetch(
                _request(
                    start=datetime(2026, 1, 1, 2, tzinfo=local_zone),
                    end=datetime(2026, 1, 1, 3, tzinfo=local_zone),
                    point=ClimatePoint(latitude=-1.26, longitude=36.76),
                )
            )
        ]

    assert len(captured) == 1
    assert "/2025/chirps-v3.0.rnl.2025.12.31.tif" in captured[0]
    assert len(values) == 1
    assert values[0].value == 0.0
    assert values[0].observed_at == datetime(2025, 12, 31, tzinfo=UTC)


@pytest.mark.asyncio
async def test_chirps_retries_transient_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    monkeypatch.setattr(chirps.asyncio, "sleep", lambda delay: _no_sleep())

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary connection failure", request=request)
        return httpx.Response(200, content=b"test-geotiff")

    monkeypatch.setattr(
        chirps,
        "_decode_geotiff",
        lambda content, point, area, max_cells: [(-1.25, 36.75, 1.0)],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CHIRPSProvider(client=client, max_retries=1)
        values = [
            item
            async for item in provider.fetch(
                _request(point=ClimatePoint(latitude=-1.26, longitude=36.76))
            )
        ]

    assert attempts == 2
    assert len(values) == 1


async def _no_sleep() -> None:
    return None


@pytest.mark.asyncio
async def test_chirps_fails_clearly_when_daily_raster_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CHIRPSProvider(client=client)
        with pytest.raises(ValueError, match="raster is unavailable"):
            await anext(
                provider.fetch(
                    _request(point=ClimatePoint(latitude=-1.26, longitude=36.76))
                )
            )


@pytest.mark.asyncio
async def test_chirps_requires_exactly_one_spatial_request_shape() -> None:
    provider = CHIRPSProvider()
    request = _request()
    with pytest.raises(ValueError, match="exactly one"):
        await anext(provider.fetch(request))


def test_chirps_validates_variant_and_date_limit() -> None:
    with pytest.raises(ValueError, match="variant"):
        CHIRPSProvider(variant="unknown")
    with pytest.raises(ValueError, match="positive"):
        CHIRPSProvider(max_days=0)
