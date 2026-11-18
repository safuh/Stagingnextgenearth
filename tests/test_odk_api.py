"""ODK Central import tests: mapping, deduplication, review queue, and tenant isolation."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _auth(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    assert (
        client.post(
            "/api/auth/register", json={"identifier": identifier, "password": password}
        ).status_code
        == 201
    )
    response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_odk_import_maps_deduplicates_and_keeps_observations_pending(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk.db'}"
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
        owner = _auth(client, "odk-owner@example.org")
        other = _auth(client, "odk-outsider@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "ODK Field Team", "slug": "odk-field-team"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/odk"
        payload = {
            "form_id": "community-rainfall-v1",
            "mapping": {
                "observed_at": "date_observed",
                "variable": "measurement",
                "value": "reading",
                "unit": "units",
                "latitude": "gps_lat",
                "longitude": "gps_lon",
            },
            "submissions": [
                {
                    "instanceId": "uuid:field-0001",
                    "data": {
                        "date_observed": "2026-11-18T08:30:00+03:00",
                        "measurement": "precipitation",
                        "reading": "14.75",
                        "units": "mm",
                        "gps_lat": "-0.681",
                        "gps_lon": "34.767",
                        "respondent_name": "not retained",
                    },
                }
            ],
        }
        imported = client.post(f"{base}/imports", headers=owner, json=payload)
        assert imported.status_code == 200, imported.text
        assert imported.json()["received"] == 1
        assert imported.json()["imported"] == 1
        assert imported.json()["skipped_duplicates"] == 0

        duplicate = client.post(f"{base}/imports", headers=owner, json=payload)
        assert duplicate.status_code == 200
        assert duplicate.json()["imported"] == 0
        assert duplicate.json()["skipped_duplicates"] == 1

        observations = client.get(
            f"/api/organizations/{organization_id}/climate-observations?quality_status=pending",
            headers=owner,
        )
        assert observations.status_code == 200
        assert len(observations.json()) == 1
        row = observations.json()[0]
        assert row["variable"] == "precipitation"
        assert row["value"] == 14.75
        assert row["quality_status"] == "pending"
        assert "respondent_name" not in str(row["metadata_json"])

        integration_status = client.get(f"{base}/status", headers=owner)
        assert integration_status.status_code == 200
        assert integration_status.json() == {
            "provider": "odk-central",
            "imported_observations": 1,
            "pending_review": 1,
        }
        assert client.post(f"{base}/imports", headers=other, json=payload).status_code == 404


def test_odk_import_rejects_bad_coordinates_and_naive_timestamps(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-invalid.db'}"
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
        owner = _auth(client, "odk-invalid-owner@example.org")
        org = client.post(
            "/api/organizations", headers=owner, json={"name": "ODK Invalid", "slug": "odk-invalid"}
        )
        base = f"/api/organizations/{org.json()['id']}/odk/imports"
        payload = {
            "form_id": "rain-v1",
            "mapping": {
                "observed_at": "when",
                "variable": "what",
                "value": "value",
                "unit": "unit",
                "latitude": "lat",
                "longitude": "lon",
            },
            "submissions": [
                {
                    "instanceId": "uuid:bad",
                    "data": {
                        "when": "2026-11-18T08:00:00",
                        "what": "rain",
                        "value": 1,
                        "unit": "mm",
                        "lat": 95,
                        "lon": 34,
                    },
                }
            ],
        }
        response = client.post(base, headers=owner, json=payload)
        assert response.status_code == 422
        payload["submissions"][0]["data"]["when"] = "2026-11-18T08:00:00+00:00"
        response = client.post(base, headers=owner, json=payload)
        assert response.status_code == 422
