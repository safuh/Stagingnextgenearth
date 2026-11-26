"""HTTP tests for bounded daily climate research time series."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _auth(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    assert client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": password},
    ).status_code == 201
    response = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_daily_series_groups_utc_days_and_units_and_excludes_rejected(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-series-api.db'}"
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "climate-series-owner@example.org")
        outsider = _auth(client, "climate-series-outsider@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate Series", "slug": "climate-series"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/climate-observations"

        for timestamp, value, unit in (
            ("2026-01-01T23:30:00-02:00", 10.0, "mm/day"),
            ("2026-01-02T01:00:00+00:00", 20.0, "mm/day"),
            ("2026-01-02T02:00:00+00:00", 40.0, "cm"),
        ):
            response = client.post(
                base,
                headers=owner,
                json={
                    "observed_at": timestamp,
                    "variable": "precipitation",
                    "value": value,
                    "unit": unit,
                    "latitude": -1.286,
                    "longitude": 36.817,
                    "source": "field station",
                },
            )
            assert response.status_code == 201

        # A rejected record must never enter either verified or pending output.
        pending = client.get(
            f"{base}/daily-series",
            headers=owner,
            params={
                "variable": "precipitation",
                "start": "2026-01-01T00:00:00+00:00",
                "end": "2026-01-04T00:00:00+00:00",
                "quality_status": "pending",
            },
        )
        assert pending.status_code == 200
        body = pending.json()
        assert body["observation_count"] == 3
        assert body["aggregation"] == "utc_day_mean_min_max"
        assert body["missing_data_policy"] == "observed_days_only_no_imputation"
        assert [(point["day"], point["unit"]) for point in body["points"]] == [
            ("2026-01-02", "cm"),
            ("2026-01-02", "mm/day"),
        ]
        mm_day = body["points"][1]
        assert mm_day["count"] == 2
        assert mm_day["mean"] == 15
        assert mm_day["minimum"] == 10
        assert mm_day["maximum"] == 20

        # The default is reviewed data, not unreviewed ingestion.
        verified = client.get(
            f"{base}/daily-series",
            headers=owner,
            params={
                "variable": "precipitation",
                "start": "2026-01-01T00:00:00+00:00",
                "end": "2026-01-04T00:00:00+00:00",
            },
        )
        assert verified.status_code == 200
        assert verified.json()["observation_count"] == 0

        hidden = client.get(
            f"/api/organizations/{organization_id}/climate-observations/daily-series",
            headers=outsider,
            params={
                "variable": "precipitation",
                "start": "2026-01-01T00:00:00+00:00",
                "end": "2026-01-04T00:00:00+00:00",
            },
        )
        assert hidden.status_code == 404

        invalid = client.get(
            f"{base}/daily-series",
            headers=owner,
            params={
                "variable": "precipitation",
                "start": "2026-01-04T00:00:00+00:00",
                "end": "2026-01-01T00:00:00+00:00",
            },
        )
        assert invalid.status_code == 422
