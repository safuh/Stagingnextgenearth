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
        partner = _auth(client, "ops-partner@example.org")
        org = client.post(
            "/api/organizations",
            headers=manager,
            json={"name": "Operations Test", "slug": "operations-test"},
        )
        assert org.status_code == 201
        org_id = org.json()["id"]
        invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=manager,
            json={"identifier": "ops-partner@example.org", "role": "institutional_partner"},
        )
        assert invitation.status_code == 201
        accepted_partner = client.post(
            f"/api/organizations/{org_id}/memberships/{invitation.json()['id']}/accept",
            headers=partner,
        )
        assert accepted_partner.status_code == 200
        programmes = f"/api/organizations/{org_id}/programmes"
        programme = client.post(
            programmes,
            headers=manager,
            json={"title": "Tree growing programme", "slug": "tree-growing"},
        )
        assert programme.status_code == 201
        base = f"{programmes}/{programme.json()['id']}"

        # Existing active youth volunteers can apply to additional programmes.
        member_volunteer = _auth(client, "ops-member-volunteer@example.org")
        member_invitation = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=manager,
            json={"identifier": "ops-member-volunteer@example.org", "role": "youth_volunteer"},
        )
        assert member_invitation.status_code == 201
        member_acceptance = client.post(
            f"/api/organizations/{org_id}/memberships/{member_invitation.json()['id']}/accept",
            headers=member_volunteer,
        )
        assert member_acceptance.status_code == 200
        member_application = client.post(
            f"{base}/volunteer-applications",
            headers=member_volunteer,
            json={
                "participation_type": "ambassador",
                "interest": "I can support local outreach and environmental learning activities.",
                "availability": "School holidays",
            },
        )
        assert member_application.status_code == 201
        member_approval = client.post(
            f"{base}/volunteer-applications/{member_application.json()['id']}/decision",
            headers=manager,
            json={"decision": "approved"},
        )
        assert member_approval.status_code == 200
        assert member_approval.json()["status"] == "approved"
        assert client.get(
            f"/api/organizations/{org_id}/memberships/me", headers=member_volunteer
        ).json()["role"] == "youth_volunteer"

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
        personal_applications = client.get(
            f"/api/organizations/{org_id}/my-volunteer-applications",
            headers=participant,
        )
        assert personal_applications.status_code == 200
        assert [item["id"] for item in personal_applications.json()] == [application_id]
        assert client.get(
            f"/api/organizations/{org_id}/my-volunteer-applications",
            headers=manager,
        ).json() == []
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
        personal_allocations = client.get(
            f"/api/organizations/{org_id}/my-volunteer-allocations",
            headers=participant,
        )
        assert personal_allocations.status_code == 200
        assert personal_allocations.json()[0]["activity_title"] == "Community planting day"
        assert client.get(
            f"/api/organizations/{org_id}/my-volunteer-allocations",
            headers=manager,
        ).json() == []
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
        duplicate_indicator = client.post(
            f"{base}/indicators",
            headers=manager,
            json={
                "key": "trees_established",
                "title": "Duplicate trees indicator",
                "unit": "trees",
            },
        )
        assert duplicate_indicator.status_code == 409
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

        participation = client.post(
            f"{base}/participation",
            headers=manager,
            json={
                "participant_group": "school",
                "group_name": "Local school environmental club",
                "participant_count": 32,
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
                "notes": "Aggregate attendance from the club register",
            },
        )
        assert participation.status_code == 201
        assert participation.json()["participant_count"] == 32
        participation_list = client.get(f"{base}/participation", headers=participant)
        assert participation_list.status_code == 200
        assert participation_list.json()[0]["participant_group"] == "school"
        small_cohort = client.post(
            f"{base}/participation",
            headers=manager,
            json={
                "participant_group": "youth_group",
                "group_name": "Small pilot group",
                "participant_count": 4,
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
            },
        )
        assert small_cohort.status_code == 201
        partner_report = client.get(f"{base}/partner-reporting", headers=partner)
        assert partner_report.status_code == 200
        report_body = partner_report.json()
        assert report_body["programme_title"] == "Tree growing programme"
        assert report_body["indicators"][0]["latest_value"] == 250
        assert report_body["participation"] == [{
            "participant_group": "school",
            "participant_count": 32,
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
        }]
        assert "recorded_by" not in report_body["participation"][0]
        assert client.get(f"{base}/partner-reporting", headers=participant).status_code == 403
        assert client.get(
            f"/api/organizations/{org_id}/programmes/not-a-programme/partner-reporting",
            headers=partner,
        ).status_code == 404

        goal = client.post(
            f"{base}/goals",
            headers=manager,
            json={"title": "Restore native woodland", "target_date": "2027-12-31"},
        )
        assert goal.status_code == 201
        goal_id = goal.json()["id"]
        assert client.post(
            f"{base}/goals/{goal_id}/status",
            headers=manager,
            json={"status": "active"},
        ).json()["status"] == "active"
        milestone = client.post(
            f"{base}/goals/{goal_id}/milestones",
            headers=manager,
            json={"title": "Complete baseline survey", "due_date": "2027-02-01"},
        )
        assert milestone.status_code == 201
        milestone_id = milestone.json()["id"]
        assert client.post(
            f"{base}/milestones/{milestone_id}/status",
            headers=manager,
            json={"status": "in_progress"},
        ).json()["status"] == "in_progress"
        task = client.post(
            f"{base}/assignments",
            headers=manager,
            json={
                "title": "Collect site observations",
                "assigned_to": application.json()["user_id"],
                "milestone_id": milestone_id,
                "priority": "high",
                "due_date": "2027-01-20",
            },
        )
        assert task.status_code == 201
        task_id = task.json()["id"]
        assert client.get(f"{base}/assignments", headers=participant).json()[0]["id"] == task_id
        assert client.post(
            f"{base}/assignments/{task_id}/status",
            headers=participant,
            json={"status": "in_progress"},
        ).json()["status"] == "in_progress"
        assert client.post(
            f"{base}/assignments/{task_id}/status",
            headers=participant,
            json={"status": "completed"},
        ).json()["completed_at"] is not None
        assert client.post(
            f"{base}/assignments/{task_id}/status",
            headers=participant,
            json={"status": "in_progress"},
        ).status_code == 409
        assert client.get(f"{base}/goals", headers=participant).status_code == 200
        assert client.get(f"{base}/milestones", headers=participant).status_code == 200
