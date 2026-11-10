"""End-to-end tests for tenant-scoped learning management."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _register(client: TestClient, identifier: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_learning_course_lifecycle_and_certificate_verification(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'learning.db'}"
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
        admin_headers = _register(client, "learning-admin@example.org")
        learner_headers = _register(client, "learning-learner@example.org")
        organisation = client.post(
            "/api/organizations",
            headers=admin_headers,
            json={"name": "Learning Lab", "slug": "learning-lab"},
        )
        assert organisation.status_code == 201
        org_id = organisation.json()["id"]
        invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=admin_headers,
            json={"identifier": "learning-learner@example.org", "role": "youth_volunteer"},
        )
        assert invitation.status_code == 201
        accepted = client.post(
            f"/api/organizations/{org_id}/memberships/{invitation.json()['id']}/accept",
            headers=learner_headers,
        )
        assert accepted.status_code == 200

        base = f"/api/organizations/{org_id}/learning"
        course_response = client.post(
            f"{base}/courses",
            headers=admin_headers,
            json={
                "title": "Community Climate Action",
                "slug": "community-climate-action",
                "description": "Practical climate literacy and community action.",
                "category": "climate",
                "delivery_mode": "blended",
            },
        )
        assert course_response.status_code == 201
        course_id = course_response.json()["id"]

        module = client.post(
            f"{base}/courses/{course_id}/modules",
            headers=admin_headers,
            json={"title": "Climate foundations", "position": 1},
        )
        assert module.status_code == 201
        lesson = client.post(
            f"{base}/modules/{module.json()['id']}/lessons",
            headers=admin_headers,
            json={
                "title": "Local climate risks",
                "content_type": "text",
                "content": "Identify locally observed climate risks.",
                "position": 1,
            },
        )
        assert lesson.status_code == 201

        published = client.post(
            f"{base}/courses/{course_id}/publish",
            headers=admin_headers,
        )
        assert published.status_code == 200
        application = client.post(
            f"{base}/courses/{course_id}/enrollments",
            headers=learner_headers,
        )
        assert application.status_code == 201
        from stagingnextgenearth.auth import TokenService

        learner_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "learning-learner@example.org",
                "password": "correct horse battery staple",
            },
        )
        assert learner_login.status_code == 200
        learner_id = TokenService(settings.jwt_secret_key.get_secret_value()).decode(
            learner_login.json()["access_token"], expected_type="access"
        )["sub"]
        decision = client.post(
            f"{base}/courses/{course_id}/enrollments/{learner_id}/decision",
            headers=admin_headers,
            json={"decision": "approved"},
        )
        assert decision.status_code == 200

        assessment = client.post(
            f"{base}/courses/{course_id}/assessments",
            headers=admin_headers,
            json={
                "title": "Climate foundations quiz",
                "assessment_type": "quiz",
                "instructions": "Submit your responses.",
                "pass_mark": 60,
            },
        )
        assert assessment.status_code == 201
        submission = client.post(
            f"{base}/assessments/{assessment.json()['id']}/submissions",
            headers=learner_headers,
            json={"submission": {"answers": ["risk", "adaptation"]}},
        )
        assert submission.status_code == 201
        evaluated = client.post(
            f"{base}/submissions/{submission.json()['id']}/evaluate",
            headers=admin_headers,
            json={"score": 85, "feedback": "Good application of the concepts."},
        )
        assert evaluated.status_code == 200

        learner_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "learning-learner@example.org",
                "password": "correct horse battery staple",
            },
        )
        assert learner_login.status_code == 200
        progress = client.post(
            f"{base}/courses/{course_id}/enrollments/{learner_id}/progress",
            headers=learner_headers,
            params={"progress_percent": 100},
        )
        assert progress.status_code == 200
        assert progress.json()["status"] == "completed"
        assert progress.json()["certificate_number"].startswith("NGE-")
        verified = client.get(
            f"{base}/certificates/verify/{progress.json()['verification_code']}",
            headers=admin_headers,
        )
        assert verified.status_code == 200
        assert verified.json()["valid"] is True

        attendance = client.post(
            f"{base}/courses/{course_id}/attendance",
            headers=admin_headers,
            json={
                "session_key": "workshop-2026-01",
                "session_title": "Community climate workshop",
                "session_date": "2026-11-10",
                "learner_id": learner_id,
                "attendance_status": "present",
            },
        )
        assert attendance.status_code == 201
        summary = client.get(
            f"{base}/courses/{course_id}/progress",
            headers=admin_headers,
        )
        assert summary.status_code == 200
        assert summary.json()["completed"] == 1
