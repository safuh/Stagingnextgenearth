"""HTTP tests for climate screening and missing-data reports."""

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


def test_climate_flagged_report_and_daily_missingness_are_tenant_scoped(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-reporting.db'}"
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
        owner = _auth(client, "climate-report-owner@example.org")
        other = _auth(client, "climate-report-other@example.org")
        created_org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate Reports", "slug": "climate-reports"},
        )
        assert created_org.status_code == 201
        organization_id = created_org.json()["id"]
        base = f"/api/organizations/{organization_id}/climate-observations"

        observations = (
            {
                "observed_at": "2026-01-01T10:00:00+00:00",
                "variable": "relative_humidity",
                "value": 125.0,
                "unit": "%",
                "quality_status": "pending",
                "metadata_json": {
                    "quality_screening_flags": ["outside_broad_physical_range"]
                },
            },
            {
                "observed_at": "2026-01-02T10:00:00+00:00",
                "variable": "relative_humidity",
                "value": 50.0,
                "unit": "%",
                "quality_status": "rejected",
                "metadata_json": {"quality_screening_flags": []},
            },
        )
        for item in observations:
            body = {
                key: value
                for key, value in item.items()
                if key != "quality_status"
            }
            body.update(
                {
                    "latitude": -1.286,
                    "longitude": 36.817,
                    "source": "field station",
                }
            )
            response = client.post(base, headers=owner, json=body)
            assert response.status_code == 201, response.text
            if item["quality_status"] == "rejected":
                rejected = client.post(
                    f"{base}/{response.json()['id']}/review",
                    headers=_auth(client, "climate-reviewer@example.org"),
                    json={"decision": "rejected", "note": "Rejected for test"},
                )
                # The creator cannot review their own record; the second
                # account must first be granted membership, so this path is
                # intentionally not used to manufacture a rejected status.
                assert rejected.status_code in {403, 404}

        flagged = client.get(f"{base}/flagged", headers=owner)
        assert flagged.status_code == 200
        report = flagged.json()
        assert report["matched_count"] == 1
        assert report["items"][0]["flags"] == ["outside_broad_physical_range"]
        assert report["scan_truncated"] is False

        filtered = client.get(
            f"{base}/flagged",
            headers=owner,
            params={"flag": "unsupported_unit"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["matched_count"] == 0

        coverage = client.get(
            f"{base}/coverage",
            headers=owner,
            params={
                "variable": "relative_humidity",
                "latitude": -1.286,
                "longitude": 36.817,
                "start_date": "2026-01-01",
                "end_date": "2026-01-03",
            },
        )
        assert coverage.status_code == 200
        assert coverage.json()["expected_days"] == 3
        assert coverage.json()["observed_days"] == 2
        assert coverage.json()["missing_days"] == ["2026-01-03"]
        assert coverage.json()["coverage_ratio"] == 0.666667
        assert coverage.json()["missing_data_policy"] == "report_only_no_imputation"

        assert client.get(
            f"{base}/flagged",
            headers=other,
        ).status_code == 404
