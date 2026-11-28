"""Tests for tenant climate-ingestion orchestration request validation."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from stagingnextgenearth.api import climate_ingestion as climate_ingestion_api
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



@pytest.mark.asyncio
async def test_chirps_guard_enforces_persisted_cooldown_between_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __init__(self, last_run: object) -> None:
            self.calls = 0
            self.last_run = last_run

        async def scalar(self, statement: object, params: object | None = None) -> object:
            self.calls += 1
            return True if self.calls == 1 else self.last_run

    monkeypatch.setattr(climate_ingestion_api.asyncio, "sleep", fake_sleep)
    session = FakeSession(
        SimpleNamespace(
            finished_at=datetime.now(UTC) - timedelta(milliseconds=100),
            error_summary=None,
        )
    )

    async with _provider_ingestion_guard(session, "chirps-v3"):
        pass

    assert session.calls == 2
    assert len(delays) == 1
    assert 0.8 <= delays[0] <= 1.1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_summary",
    [
        "ClimateProviderUnavailable: climate provider stream failed",
        "ConnectTimeout: climate provider stream failed",
    ],
)
async def test_chirps_guard_enforces_provider_block_cooldown(
    error_summary: str,
) -> None:
    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __init__(self) -> None:
            self.calls = 0

        async def scalar(self, statement: object, params: object | None = None) -> object:
            self.calls += 1
            if self.calls == 1:
                return True
            return SimpleNamespace(
                finished_at=datetime.now(UTC) - timedelta(hours=1),
                error_summary=error_summary,
            )

    session = FakeSession()
    with pytest.raises(HTTPException) as exc:
        async with _provider_ingestion_guard(session, "chirps-v3"):
            pytest.fail("provider-block cooldown should reject a new ingestion")

    assert exc.value.status_code == 503
    assert int(exc.value.headers["Retry-After"]) > 0
    assert session.calls == 2


@pytest.mark.asyncio
async def test_chirps_guard_rejects_a_concurrent_run() -> None:
    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def scalar(self, statement: object, params: object | None = None) -> object:
            return False

    with pytest.raises(HTTPException) as exc:
        async with _provider_ingestion_guard(FakeSession(), "chirps-v3"):
            pytest.fail("a concurrent CHIRPS run should not acquire the lock")

    assert exc.value.status_code == 409
