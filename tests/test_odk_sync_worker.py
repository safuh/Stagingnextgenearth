"""Automated ODK Central poller tests with a deterministic Central client."""

import asyncio
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.platform.models import ClimateObservation, ODKConnection, ODKSyncRun
from stagingnextgenearth.workers import odk_sync


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


def test_worker_imports_and_deduplicates_central_odata_submissions(
    monkeypatch, tmp_path: Path
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-worker.db'}"
    key = Fernet.generate_key().decode()
    engine = create_async_engine(url)

    async def prepare() -> None:
        from stagingnextgenearth.core.database import Base

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
        odk_encryption_key=key,
    )

    class FakeCentral:
        def __init__(self, base_url: str, email: str, password: str) -> None:
            assert base_url == "https://central.example.org"
            assert email == "field@example.org"
            assert password == "odk-secret"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def list_forms(self, project_id: int):
            assert project_id == 22
            return [{"xmlFormId": "rainfall-v2", "name": "Rainfall"}]

        async def submission_pages(self, project_id: int, form_id: str, cursor: str | None = None):
            assert project_id == 22
            assert form_id == "rainfall-v2"

            def row(number: int) -> dict[str, object]:
                record = {
                    "__id": f"uuid:rainfall-{number:04d}",
                    "__system": {"submissionDate": "2026-11-18T08:30:00Z"},
                    "measurement": "rainfall",
                    "value": number + 0.25,
                    "unit": "mm",
                    "latitude": -0.681,
                    "longitude": 34.767,
                }
                if number == 0:
                    record.pop("latitude")
                return record

            if cursor is not None:
                assert cursor.endswith("$skiptoken=page-11")
                yield [row(10)], None
                return
            for number in range(10):
                yield (
                    [row(number)],
                    (
                        "https://central.example.org/v1/projects/22/forms/"
                        "rainfall-v2.svc/Submissions?$skiptoken=page-"
                        f"{number + 2}"
                    ),
                )
            raise ValueError("ODK Central form exceeded the per-run pagination limit")

    monkeypatch.setattr(odk_sync, "ODKCentralClient", FakeCentral)
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "odk-worker-owner@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "ODK Worker Team", "slug": "odk-worker-team"},
        )
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/odk"
        saved = client.put(
            f"{base}/connection",
            headers=owner,
            json={
                "base_url": "https://central.example.org",
                "project_id": 22,
                "account_email": "field@example.org",
                "password": "odk-secret",
                "form_mappings": {
                    "rainfall-v2": {
                        "observed_at": "__system/submissionDate",
                        "variable": "measurement",
                        "value": "value",
                        "unit": "unit",
                        "latitude": "latitude",
                        "longitude": "longitude",
                    }
                },
            },
        )
        assert saved.status_code == 200, saved.text

        async def run_three_times() -> tuple[
            dict, dict, dict, list[ClimateObservation], list[ODKSyncRun]
        ]:
            db_engine = create_async_engine(url)
            factory = async_sessionmaker(db_engine, expire_on_commit=False)
            try:
                async with factory() as session:
                    connection = await session.scalar(
                        select(ODKConnection).where(
                            ODKConnection.organization_id == organization_id
                        )
                    )
                    assert connection is not None
                    connection_id = connection.id
                first = await odk_sync.sync_odk_connection(
                    factory, connection_id, encryption_key=key
                )
                second = await odk_sync.sync_odk_connection(
                    factory, connection_id, encryption_key=key
                )
                third = await odk_sync.sync_odk_connection(
                    factory, connection_id, encryption_key=key
                )
                async with factory() as session:
                    observations = list((await session.scalars(select(ClimateObservation))).all())
                    runs = list((await session.scalars(select(ODKSyncRun))).all())
                return first, second, third, observations, runs
            finally:
                await db_engine.dispose()

        first, second, third, observations, runs = asyncio.run(run_three_times())
        assert first == {
            "status": "partial",
            "forms": 1,
            "received": 10,
            "imported": 9,
            "duplicates": 0,
            "rejected": 1,
            "errors": 2,
        }
        assert second == {
            "status": "succeeded",
            "forms": 1,
            "received": 1,
            "imported": 1,
            "duplicates": 0,
            "rejected": 0,
            "errors": 0,
        }
        assert third == {
            "status": "partial",
            "forms": 1,
            "received": 10,
            "imported": 0,
            "duplicates": 9,
            "rejected": 1,
            "errors": 2,
        }
        assert len(observations) == 10
        assert all(item.quality_status == "pending" for item in observations)
        assert {item.value for item in observations} == {number + 0.25 for number in range(1, 11)}
        assert len(runs) == 3
        assert [run.rejected_count for run in runs] == [1, 0, 1]


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "rejected the integration credentials"),
        (403, "denied access to the configured project or form"),
        (410, "pagination cursor expired"),
        (429, "rate-limited the integration"),
    ],
)
def test_central_http_errors_are_classified_without_exposing_response_text(
    status_code: int, expected: str
) -> None:
    request = httpx.Request("GET", "https://central.example.org/submissions")
    response = httpx.Response(status_code, request=request, text="private response payload")
    error = httpx.HTTPStatusError("private request detail", request=request, response=response)
    message = odk_sync._safe_central_error(error)
    assert expected in message
    assert "private" not in message
