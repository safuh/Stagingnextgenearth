"""HTTP tests for tenant-scoped climate quality summaries."""

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


def test_climate_quality_summary_is_tenant_scoped_and_time_bounded(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-quality-api.db'}"
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
        owner = _auth(client, "climate-quality-owner@example.org")
        other = _auth(client, "climate-quality-other@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate QA", "slug": "climate-qa"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/climate-observations"

        for observed_at, variable, value, unit in (
            ("2026-01-05T00:00:00+00:00", "precipitation", 12.0, "mm"),
            ("2026-01-15T00:00:00+00:00", "air_temperature_2m", 25.0, "degC"),
        ):
            created = client.post(
                base,
                headers=owner,
                json={
                    "observed_at": observed_at,
                    "variable": variable,
                    "value": value,
                    "unit": unit,
                    "latitude": -1.286,
                    "longitude": 36.817,
                    "source": "manual field observation",
                },
            )
            assert created.status_code == 201

        summary = client.get(f"{base}/quality-summary", headers=owner)
        assert summary.status_code == 200
        assert summary.json() == {
            "total": 2,
            "by_status": {"pending": 2},
            "by_variable": {"air_temperature_2m": 1, "precipitation": 1},
        }

        bounded = client.get(
            f"{base}/quality-summary",
            headers=owner,
            params={
                "start": "2026-01-10T00:00:00+00:00",
                "end": "2026-02-01T00:00:00+00:00",
            },
        )
        assert bounded.status_code == 200
        assert bounded.json()["total"] == 1
        assert bounded.json()["by_variable"] == {"air_temperature_2m": 1}

        invalid = client.get(
            f"{base}/quality-summary",
            headers=owner,
            params={
                "start": "2026-02-01T00:00:00+00:00",
                "end": "2026-01-01T00:00:00+00:00",
            },
        )
        assert invalid.status_code == 422

        assert client.get(
            f"/api/organizations/{organization_id}/climate-observations/quality-summary",
            headers=other,
        ).status_code == 403
