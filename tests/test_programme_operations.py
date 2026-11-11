"""Tests for programme activity scheduling and participant assignment."""

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
    login = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_programme_activity_and_participant_allocation(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'programme-operations.db'}"
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
        manager = _auth(client, "ops-manager@example.org")
        participant = _auth(client, "ops-participant@example.org")
        org = client.post(
            "/api/organizations",
            headers=manager,
            json={"name": "Operations Test", "slug": "operations-test"},
        )
        assert org.status_code == 201
        org_id = org.json()["id"]
        programmes = f"/api/organizations/{org_id}/programmes"
        programme = client.post(
            programmes,
            headers=manager,
            json={"title": "Tree growing programme", "slug": "tree-growing"},
        )
        assert programme.status_code == 201
        base = f"{programmes}/{programme.json()['id']}"

        application = client.post(
            f"{base}/volunteer-applications",
            headers=participant,
            json={
                "participation_type": "volunteer",
                "interest": "I want to support community tree growing and monitoring.",
                "availability": "Weekends",
            },
        )
        assert application.status_code == 201
        application_id = application.json()["id"]
        assert application.json()["status"] == "pending"
        assert client.post(
            f"{base}/volunteer-applications",
            headers=participant,
            json={
                "participation_type": "volunteer",
                "interest": "I want to support community tree growing and monitoring.",
            },
        ).status_code == 409

        approved = client.post(
            f"{base}/volunteer-applications/{application_id}/decision",
            headers=manager,
            json={"decision": "approved"},
        )
        assert approved.status_code == 200
        activity = client.post(
            f"{base}/activities",
            headers=manager,
            json={
                "title": "Community planting day",
                "location": "Kisii",
                "start_at": "2026-12-01T08:00:00+03:00",
                "end_at": "2026-12-01T12:00:00+03:00",
            },
        )
        assert activity.status_code == 201
        activity_id = activity.json()["id"]
        started = client.post(
            f"{base}/activities/{activity_id}/status",
            headers=manager,
            json={"status": "in_progress"},
        )
        assert started.status_code == 200
        completed = client.post(
            f"{base}/activities/{activity_id}/status",
            headers=manager,
            json={"status": "completed"},
        )
        assert completed.status_code == 200
        invalid_transition = client.post(
            f"{base}/activities/{activity_id}/status",
            headers=manager,
            json={"status": "in_progress"},
        )
        assert invalid_transition.status_code == 409
        assert client.get(f"{base}/activities", headers=participant).status_code == 200
        assignment = client.post(
            f"{base}/activities/{activity_id}/volunteers",
            headers=manager,
            json={"user_id": application.json()["user_id"]},
        )
        assert assignment.status_code == 201
        assert assignment.json()["status"] == "assigned"
        duplicate = client.post(
            f"{base}/activities/{activity_id}/volunteers",
            headers=manager,
            json={"user_id": application.json()["user_id"]},
        )
        assert duplicate.status_code == 409

        indicator = client.post(
            f"{base}/indicators",
            headers=manager,
            json={
                "key": "trees_established",
                "title": "Trees established",
                "unit": "trees",
                "direction": "increase",
                "baseline_value": 0,
                "target_value": 1000,
            },
        )
        assert indicator.status_code == 201
        indicator_id = indicator.json()["id"]
        measurement = client.post(
            f"{base}/indicators/{indicator_id}/measurements",
            headers=manager,
            json={
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
                "value": 250,
                "notes": "Verified planting register total",
            },
        )
        assert measurement.status_code == 201
        progress = client.get(f"{base}/indicators", headers=participant)
        assert progress.status_code == 200
        assert progress.json()[0]["latest_measurement"]["value"] == 250
        assert progress.json()[0]["progress_percent"] == 25
        history = client.get(
            f"{base}/indicators/{indicator_id}/measurements",
            headers=participant,
        )
        assert history.status_code == 200
        assert len(history.json()) == 1
