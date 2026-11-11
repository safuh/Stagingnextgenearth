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
