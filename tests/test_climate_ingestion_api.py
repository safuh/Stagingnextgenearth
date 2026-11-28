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
from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderUnavailable,
)


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


@pytest.mark.asyncio
async def test_chirps_provider_block_response_includes_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def __init__(self) -> None:
            self.commits = 0

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            pass

    async def allow_ingestion(*_args: object) -> bool:
        return True

    async def blocked_provider(*_args: object, **_kwargs: object) -> None:
        raise ClimateProviderUnavailable(
            "CHIRPS denied the request (HTTP 429). Stop retries and wait several hours."
        )

    provider = SimpleNamespace(
        provider_id="chirps-v3",
        source_name="CHIRPS v3",
        licence="CC-BY-4.0",
        fetch=lambda _request: None,
    )
    monkeypatch.setattr(climate_ingestion_api, "membership_has_any_role", allow_ingestion)
    monkeypatch.setattr(climate_ingestion_api, "_provider_for", lambda _body: provider)
    monkeypatch.setattr(
        climate_ingestion_api,
        "persist_provider_measurements",
        blocked_provider,
    )
    session = FakeSession()
    body = ClimateIngestionCreate(
        provider="chirps-v3",
        **_period(),
        area={"west": 36.7, "south": -1.3, "east": 36.8, "north": -1.2},
    )

    with pytest.raises(HTTPException) as exc:
        await climate_ingestion_api.run_climate_ingestion(
            organization_id="org-1",
            body=body,
            principal=SimpleNamespace(user_id="researcher-1"),
            membership=SimpleNamespace(),
            session=session,
        )

    assert exc.value.status_code == 503
    assert exc.value.headers is not None
    assert exc.value.headers["Retry-After"] == "10800"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_cooldown_status_reports_persisted_chirps_block_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allow_status(*_args: object) -> bool:
        return True

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalar(self, _statement: object) -> object:
            self.calls += 1
            return SimpleNamespace(
                finished_at=datetime.now(UTC) - timedelta(hours=1),
                error_summary="ClimateProviderUnavailable: CHIRPS returned HTTP 429",
            )

    monkeypatch.setattr(climate_ingestion_api, "membership_has_any_role", allow_status)
    session = FakeSession()
    result = await climate_ingestion_api.get_climate_provider_cooldown(
        organization_id="org-1",
        membership=SimpleNamespace(),
        session=session,
        provider_id="chirps-v3",
    )

    assert result.active is True
    assert 7_100 <= result.retry_after_seconds <= 7_201
    assert result.retry_at is not None
    assert result.reason == "provider_block"
    assert session.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finished_at,error_summary",
    [
        (datetime.now(UTC) - timedelta(hours=4), "ClimateProviderUnavailable: HTTP 429"),
        (datetime.now(UTC) - timedelta(minutes=1), "RuntimeError: provider unavailable"),
        (None, None),
    ],
)
async def test_cooldown_status_is_inactive_without_an_active_provider_block(
    monkeypatch: pytest.MonkeyPatch,
    finished_at: datetime | None,
    error_summary: str | None,
) -> None:
    async def allow_status(*_args: object) -> bool:
        return True

    class FakeSession:
        async def scalar(self, _statement: object) -> object:
            if finished_at is None:
                return None
            return SimpleNamespace(
                finished_at=finished_at,
                error_summary=error_summary,
            )

    monkeypatch.setattr(climate_ingestion_api, "membership_has_any_role", allow_status)
    result = await climate_ingestion_api.get_climate_provider_cooldown(
        organization_id="org-1",
        membership=SimpleNamespace(),
        session=FakeSession(),
        provider_id="chirps-v3",
    )

    assert result.active is False
    assert result.retry_after_seconds == 0
    assert result.retry_at is None
    assert result.reason is None


@pytest.mark.asyncio
async def test_cooldown_status_requires_climate_ingestion_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def deny_status(*_args: object) -> bool:
        return False

    class FakeSession:
        async def scalar(self, _statement: object) -> object:
            pytest.fail("unauthorised cooldown reads must not query provider history")

    monkeypatch.setattr(climate_ingestion_api, "membership_has_any_role", deny_status)
    with pytest.raises(HTTPException) as exc:
        await climate_ingestion_api.get_climate_provider_cooldown(
            organization_id="org-1",
            membership=SimpleNamespace(),
            session=FakeSession(),
            provider_id="chirps-v3",
        )

    assert exc.value.status_code == 403
