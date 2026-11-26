"""End-to-end programme deliverable and lifecycle tests."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _headers(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    registered = client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": password},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_programme_deliverable_submission_review_and_lifecycle(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'programme-deliverables.db'}"
    engine = create_async_engine(database_url)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare_database())
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )
    with TestClient(create_app(settings)) as client:
        headers = _headers(client, "programme-manager@example.org")
        organization = client.post(
            "/api/organizations",
            headers=headers,
            json={"name": "Programme Test", "slug": "programme-test"},
        )
        assert organization.status_code == 201
        organization_id = organization.json()["id"]
        programmes_url = f"/api/organizations/{organization_id}/programmes"
        programme = client.post(
            programmes_url,
            headers=headers,
            json={"title": "Community climate action", "slug": "community-climate-action"},
        )
        assert programme.status_code == 201
        programme_id = programme.json()["id"]
        deliverables_url = f"{programmes_url}/{programme_id}/deliverables"
        deliverable = client.post(
            deliverables_url,
            headers=headers,
            json={
                "title": "Community baseline report",
                "description": "Document initial community priorities.",
            },
        )
        assert deliverable.status_code == 201
        deliverable_id = deliverable.json()["id"]
        submitted = client.post(
            f"{deliverables_url}/{deliverable_id}/submit",
            headers=headers,
            json={
                "evidence_url": "https://example.org/evidence/report",
                "note": "Ready for review",
            },
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"
        accepted = client.post(
            f"{deliverables_url}/{deliverable_id}/decision",
            headers=headers,
            json={"decision": "accepted", "note": "Evidence reviewed"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"
        listed = client.get(deliverables_url, headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        invalid_transition = client.post(
            f"{programmes_url}/{programme_id}/status",
            headers=headers,
            json={"status": "completed"},
        )
        assert invalid_transition.status_code == 409
        planned = client.post(
            f"{programmes_url}/{programme_id}/status",
            headers=headers,
            json={"status": "planned"},
        )
        assert planned.status_code == 200
        active = client.post(
            f"{programmes_url}/{programme_id}/status",
            headers=headers,
            json={"status": "active"},
        )
        assert active.status_code == 200
