"""Safeguarded programme volunteer application regression tests."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _login(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    assert client.post("/api/auth/register", json={
        "identifier": identifier, "password": password
    }).status_code == 201
    response = client.post("/api/auth/login", json={
        "identifier": identifier, "password": password
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_volunteer_application_requires_staff_safeguarding_verification(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'volunteer-applications.db'}"
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
        owner = _login(client, "volunteer-owner@example.org")
        applicant = _login(client, "volunteer-applicant@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Volunteer Test", "slug": "volunteer-test"},
        ).json()
        org_id = org["id"]
        programme = client.post(
            f"/api/organizations/{org_id}/programmes",
            headers=owner,
            json={
                "title": "Community Climate Action",
                "slug": "community-climate-action",
                "summary": "Community-led climate education and action.",
            },
        )
        assert programme.status_code == 201
        programme_id = programme.json()["id"]
        activated = client.post(
            f"/api/organizations/{org_id}/programmes/{programme_id}/status",
            headers=owner,
            json={"status": "planned"},
        )
        assert activated.status_code == 200

        endpoint = (
            f"/api/organizations/{org_id}/programmes/{programme_id}/volunteer-applications"
        )
        application = client.post(
            endpoint,
            headers=applicant,
            json={
                "participation_type": "volunteer",
                "interest": (
                    "I want to support community climate learning and local "
                    "restoration activities."
                ),
                "availability": "Weekends and school holidays",
            },
        )
        assert application.status_code == 201
        application_id = application.json()["id"]
        assert application.json()["status"] == "pending"
        assert application.json()["safeguarding_confirmed"] is False
        assert client.post(
            endpoint,
            headers=applicant,
            json={
                "participation_type": "volunteer",
                "interest": (
                    "I want to support community climate learning and local "
                    "restoration activities."
                ),
            },
        ).status_code == 409

        queue = client.get(endpoint, headers=owner)
        assert queue.status_code == 200
        assert (
            queue.json()[0]["applicant_identifier"]
            == "volunteer-applicant@example.org"
        )

        organisation_queue = client.get(
            f"/api/organizations/{org_id}/volunteer-applications",
            headers=owner,
        )
        assert organisation_queue.status_code == 200
        assert organisation_queue.json()[0]["programme_title"] == "Community Climate Action"
        assert (
            organisation_queue.json()[0]["applicant_identifier"]
            == "volunteer-applicant@example.org"
        )
        assert client.get(
            f"/api/organizations/{org_id}/volunteer-applications",
            headers=applicant,
        ).status_code == 403

        decision_url = f"{endpoint}/{application_id}/decision"
        blocked = client.post(
            decision_url,
            headers=owner,
            json={"decision": "approved"},
        )
        assert blocked.status_code == 409
        assert "safeguarding" in blocked.text.lower()

        approved = client.post(
            decision_url,
            headers=owner,
            json={
                "decision": "approved",
                "safeguarding_verified": True,
                "review_note": "Required safeguarding and guardian-consent checks completed.",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["safeguarding_confirmed"] is True

        audit = client.get(
            f"/api/organizations/{org_id}/audit-events?limit=100",
            headers=owner,
        )
        assert audit.status_code == 200
        decision_event = next(
            event for event in audit.json()
            if event["action"] == "volunteer_application.decided"
        )
        assert decision_event["subject_user_id"] == application.json()["user_id"]
        assert decision_event["changes"]["application_id"] == application_id
        assert decision_event["changes"]["decision"] == "approved"
        assert decision_event["changes"]["safeguarding_confirmed"] is True

        memberships = client.get(
            f"/api/organizations/{org_id}/memberships",
            headers=owner,
        )
        assert memberships.status_code == 200
        volunteer = next(
            item for item in memberships.json()
            if item["user_id"] == application.json()["user_id"]
        )
        assert volunteer["role"] == "youth_volunteer"
        assert volunteer["status"] == "active"
        assert client.post(
            decision_url,
            headers=owner,
            json={"decision": "rejected"},
        ).status_code == 409
