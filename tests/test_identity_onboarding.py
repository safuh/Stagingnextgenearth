"""End-to-end tests for invitation-first identity onboarding and account recovery."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str, str]] = []

    async def send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        self.messages.append((recipient, subject, text_body, html_body))

    def token(self, index: int = -1) -> str:
        body = self.messages[index][2]
        link = next(line for line in body.splitlines() if "#token=" in line)
        return link.rsplit("#token=", 1)[1]


@pytest.fixture
async def identity_client(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'identity-onboarding.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="identity-test-signing-secret-at-least-32-chars",
        public_base_url="https://nextgen.example.test",
    )
    app = create_app(settings)
    sender = FakeEmailSender()
    app.state.email_sender = sender
    with TestClient(app) as client:
        yield client, sender, tmp_path / "identity-onboarding.db"
    await engine.dispose()


def register_admin(client: TestClient, email: str = "admin@example.test") -> tuple[str, str]:
    registered = client.post(
        "/api/auth/register",
        json={"identifier": email, "password": "correct horse battery staple"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"identifier": email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    created = client.post(
        "/api/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "NextGen Test Organisation", "slug": "nextgen-test-org"},
    )
    assert created.status_code == 201
    return token, created.json()["id"]


def test_invitation_creates_new_verified_account_and_only_assigned_roles(identity_client) -> None:
    client, sender, _engine = identity_client
    admin_token, organization_id = register_admin(client)
    response = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "Learner@Example.test", "roles": ["learner", "researcher"]},
    )
    assert response.status_code == 201, response.text
    invitation = response.json()
    assert invitation["status"] == "delivered"
    assert invitation["invitation_url"] is None
    assert sender.messages[-1][0] == "learner@example.test"
    raw_token = sender.token()

    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"token": raw_token, "password": "a-long-new-password-2026"},
    )
    assert accepted.status_code == 200, accepted.text
    access_token = accepted.json()["access_token"]
    context = client.get("/api/auth/context", headers={"Authorization": f"Bearer {access_token}"})
    assert context.status_code == 200
    assert context.json()["memberships"][0]["roles"] == ["learner", "researcher"]

    replay = client.post(
        "/api/auth/invitations/accept",
        json={"token": raw_token, "password": "a-long-new-password-2026"},
    )
    assert replay.status_code == 400


def test_invitation_token_is_hashed_and_revocation_prevents_acceptance(identity_client) -> None:
    client, sender, database_path = identity_client
    admin_token, organization_id = register_admin(client, "owner2@example.test")
    response = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "invitee@example.test", "roles": ["employee"]},
    )
    assert response.status_code == 201
    raw_token = sender.token()
    invitation_id = response.json()["id"]

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        stored_hash = connection.execute(
            "SELECT token_hash FROM identity_action_tokens WHERE id = ?",
            (invitation_id,),
        ).fetchone()[0]
    assert stored_hash != raw_token

    revoked = client.delete(
        f"/api/organizations/{organization_id}/onboarding-invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoked.status_code == 204
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"token": raw_token, "password": "a-long-new-password-2026"},
    )
    assert accepted.status_code == 400


def test_password_reset_is_non_enumerating_and_revokes_old_sessions(identity_client) -> None:
    client, sender, _engine = identity_client
    registered = client.post(
        "/api/auth/register",
        json={"identifier": "reset@example.test", "password": "correct horse battery staple"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"identifier": "reset@example.test", "password": "correct horse battery staple"},
    )
    refresh_token = login.json()["refresh_token"]

    missing = client.post(
        "/api/auth/password-reset/request", json={"email": "missing@example.test"}
    )
    existing = client.post("/api/auth/password-reset/request", json={"email": "reset@example.test"})
    assert missing.status_code == existing.status_code == 202
    assert missing.json() == existing.json()
    raw_token = sender.token()
    reset = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "a-new-password-that-is-long"},
    )
    assert reset.status_code == 200
    replay = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "another-new-password-long"},
    )
    assert replay.status_code == 400
    refresh = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


def test_invitation_cannot_be_created_by_non_admin(identity_client) -> None:
    client, _sender, _engine = identity_client
    owner_token, organization_id = register_admin(client, "owner3@example.test")
    member_registration = client.post(
        "/api/auth/register",
        json={"identifier": "member@example.test", "password": "correct horse battery staple"},
    )
    assert member_registration.status_code == 201
    member_login = client.post(
        "/api/auth/login",
        json={"identifier": "member@example.test", "password": "correct horse battery staple"},
    )
    member_token = member_login.json()["access_token"]
    invited = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"identifier": "member@example.test", "role": "employee"},
    )
    assert invited.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{invited.json()['id']}/accept",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accepted.status_code == 200
    response = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"email": "another@example.test", "roles": ["learner"]},
    )
    assert response.status_code == 403


def test_email_verification_and_change_revoke_sessions(identity_client) -> None:
    client, sender, _database_path = identity_client
    email = "identity-change@example.test"
    password = "correct horse battery staple"
    assert (
        client.post(
            "/api/auth/register", json={"identifier": email, "password": password}
        ).status_code
        == 201
    )
    login = client.post("/api/auth/login", json={"identifier": email, "password": password})
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}
    requested = client.post("/api/auth/email-verification/request", headers=headers)
    assert requested.status_code == 202
    verification_token = sender.token()
    assert (
        client.post(
            "/api/auth/email-verification/confirm", json={"token": verification_token}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/email-verification/confirm", json={"token": verification_token}
        ).status_code
        == 400
    )
    changed = client.post(
        "/api/auth/email-change/request",
        headers=headers,
        json={"new_email": "updated-identity@example.test", "current_password": password},
    )
    assert changed.status_code == 202
    assert (
        client.post("/api/auth/email-change/confirm", json={"token": sender.token()}).status_code
        == 200
    )
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"identifier": "updated-identity@example.test", "password": password},
        ).status_code
        == 200
    )


def test_google_oidc_is_fail_closed_when_not_configured(identity_client) -> None:
    client, _sender, _database_path = identity_client
    assert client.get("/api/auth/google/start").status_code == 503


def test_learner_invitation_enrols_in_the_selected_published_course(identity_client) -> None:
    client, sender, database_path = identity_client
    admin_token, organization_id = register_admin(client, "course-owner@example.test")
    headers = {"Authorization": f"Bearer {admin_token}"}
    course = client.post(
        f"/api/organizations/{organization_id}/learning/courses",
        headers=headers,
        json={
            "title": "Climate Foundations",
            "slug": "climate-foundations",
            "description": "A published learner demonstration course.",
        },
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    module = client.post(
        f"/api/organizations/{organization_id}/learning/courses/{course_id}/modules",
        headers=headers,
        json={"title": "Climate basics", "position": 1},
    )
    assert module.status_code == 201, module.text
    lesson = client.post(
        f"/api/organizations/{organization_id}/learning/modules/{module.json()['id']}/lessons",
        headers=headers,
        json={
            "title": "Climate systems",
            "content_type": "text",
            "content": "Climate learning content.",
            "position": 1,
        },
    )
    assert lesson.status_code == 201, lesson.text
    published = client.post(
        f"/api/organizations/{organization_id}/learning/courses/{course_id}/publish",
        headers=headers,
    )
    assert published.status_code == 200

    learner_email = "scoped-learner@example.test"
    learner_password = "correct horse battery staple"
    registered = client.post(
        "/api/auth/register",
        json={"identifier": learner_email, "password": learner_password},
    )
    assert registered.status_code == 201
    learner_login = client.post(
        "/api/auth/login",
        json={"identifier": learner_email, "password": learner_password},
    )
    assert learner_login.status_code == 200
    applied = client.post(
        f"/api/organizations/{organization_id}/learning/courses/{course_id}/enrollments",
        headers={"Authorization": f"Bearer {learner_login.json()['access_token']}"},
    )
    assert applied.status_code == 201
    assert applied.json()["status"] == "applied"

    invited = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers=headers,
        json={"email": learner_email, "roles": ["learner"], "course_id": course_id},
    )
    assert invited.status_code == 201, invited.text
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"token": sender.token(), "password": learner_password},
    )
    assert accepted.status_code == 200, accepted.text

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        enrollments = connection.execute(
            "SELECT status, progress_percent FROM learning_enrollments WHERE course_id = ?",
            (course_id,),
        ).fetchall()
    assert enrollments == [("approved", 0)]


def test_funder_is_a_distinct_invitable_role(identity_client) -> None:
    client, sender, _database_path = identity_client
    admin_token, organization_id = register_admin(client, "funder-owner@example.test")
    invitation = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "funder-contact@example.test", "roles": ["funder"]},
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"token": sender.token(), "password": "a-long-funder-password-2026"},
    )
    assert accepted.status_code == 200, accepted.text
    context = client.get(
        "/api/auth/context",
        headers={"Authorization": f"Bearer {accepted.json()['access_token']}"},
    )
    assert context.status_code == 200
    assert context.json()["memberships"][0]["roles"] == ["funder"]

    admin_invitation = client.post(
        f"/api/organizations/{organization_id}/onboarding-invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "additional-admin@example.test", "roles": ["admin"]},
    )
    assert admin_invitation.status_code == 201, admin_invitation.text
    admin_acceptance = client.post(
        "/api/auth/invitations/accept",
        json={"token": sender.token(), "password": "correct horse battery staple"},
    )
    assert admin_acceptance.status_code == 200, admin_acceptance.text
    admin_context = client.get(
        "/api/auth/context",
        headers={"Authorization": f"Bearer {admin_acceptance.json()['access_token']}"},
    )
    assert admin_context.status_code == 200
    assert admin_context.json()["memberships"][0]["roles"] == ["admin"]
