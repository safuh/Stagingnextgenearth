"""Employment application review and employee onboarding regression tests."""
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


def test_employment_application_requires_review_before_employee_membership(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'employment-applications.db'}"
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
        owner = _login(client, "employment-owner@example.org")
        candidate = _login(client, "employment-candidate@example.org")
        org = client.post(
            "/api/organizations", headers=owner,
            json={"name": "Employment Test", "slug": "employment-test"},
        ).json()
        org_id = org["id"]
        base = f"/api/organizations/{org_id}/employment-applications"
        payload = {
            "full_name": "Example Candidate",
            "desired_position": "Climate Research Associate",
            "qualifications": "I have relevant environmental science training and research experience.",
            "experience_summary": "Supported community climate data collection projects.",
        }
        created = client.post(base, headers=candidate, json=payload)
        assert created.status_code == 201
        application_id = created.json()["id"]
        assert created.json()["status"] == "pending"
        assert client.post(base, headers=candidate, json=payload).status_code == 409
        mine = client.get(
            f"/api/organizations/{org_id}/my-employment-applications",
            headers=candidate,
        )
        assert mine.status_code == 200
        assert [item["id"] for item in mine.json()] == [application_id]

        queue = client.get(base, headers=owner)
        assert queue.status_code == 200
        assert queue.json()[0]["applicant_identifier"] == "employment-candidate@example.org"

        decision = client.post(
            f"{base}/{application_id}/decision",
            headers=owner,
            json={"decision": "approved", "note": "References and qualifications reviewed."},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "approved"
        memberships = client.get(f"/api/organizations/{org_id}/memberships", headers=owner)
        assert memberships.status_code == 200
        employee = next(item for item in memberships.json() if item["user_id"] == created.json()["user_id"])
        assert employee["role"] == "employee"
        assert employee["status"] == "active"

        people = client.get(f"/api/organizations/{org_id}/people", headers=owner)
        assert people.status_code == 200
        profile = next(item for item in people.json() if item["full_name"] == "Example Candidate")
        assert profile["person_types"] == ["employee"]
        assert profile["positions"] == ["Climate Research Associate"]
        assert profile["review_state"] == "pending"
        assert profile["visibility"] == "private"
        assert client.post(
            f"{base}/{application_id}/decision",
            headers=owner,
            json={"decision": "rejected"},
        ).status_code == 409
