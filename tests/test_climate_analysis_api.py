"""HTTP tests for tenant-scoped descriptive climate analysis."""

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


def test_climate_analysis_summary_is_bounded_unit_grouped_and_tenant_scoped(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-analysis-api.db'}"
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
        owner = _auth(client, "climate-analysis-owner@example.org")
        outsider = _auth(client, "climate-analysis-outsider@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate Analysis", "slug": "climate-analysis"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/climate-observations"
        for observed_at, value, unit in (
            ("2026-01-01T00:00:00+00:00", 10.0, "mm/day"),
            ("2026-01-02T00:00:00+00:00", 20.0, "mm/day"),
            ("2026-01-03T00:00:00+00:00", 30.0, "cm"),
        ):
            response = client.post(
                base,
                headers=owner,
                json={
                    "observed_at": observed_at,
                    "variable": "precipitation",
                    "value": value,
                    "unit": unit,
                    "latitude": -1.286,
                    "longitude": 36.817,
                    "source": "field station",
                },
            )
            assert response.status_code == 201

        params = {
            "variable": "precipitation",
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-02-01T00:00:00+00:00",
            "quality_status": "pending",
        }
        response = client.get(f"{base}/analysis-summary", headers=owner, params=params)
        assert response.status_code == 200
        body = response.json()
        assert body["observation_count"] == 3
        assert body["missing_data_policy"] == "no_imputation"
        assert body["method"] == "descriptive_hyndman_fan_type_7"
        assert [group["unit"] for group in body["groups"]] == ["cm", "mm/day"]
        assert body["groups"][0]["mean"] == 30
        assert body["groups"][1]["mean"] == 15
        assert body["groups"][1]["count"] == 2

        # Research summaries default to independently reviewed measurements.
        verified_default = client.get(
            f"{base}/analysis-summary",
            headers=owner,
            params={key: value for key, value in params.items() if key != "quality_status"},
        )
        assert verified_default.status_code == 200
        assert verified_default.json()["observation_count"] == 0

        invalid = client.get(
            f"{base}/analysis-summary",
            headers=owner,
            params={
                **params,
                "start": "2026-02-01T00:00:00+00:00",
                "end": "2026-01-01T00:00:00+00:00",
            },
        )
        assert invalid.status_code == 422
        hidden = client.get(
            f"/api/organizations/{organization_id}/climate-observations/analysis-summary",
            headers=outsider,
            params=params,
        )
        assert hidden.status_code == 404
