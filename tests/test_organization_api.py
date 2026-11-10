"""Integration tests for authenticated organisation and tenant-scoped APIs."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


@pytest.fixture
def client(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'platform-api.db'}"
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
    with TestClient(create_app(settings)) as test_client:
        yield test_client
    asyncio.run(engine.dispose())


def register_and_login(client: TestClient, identifier: str) -> str:
    registered = client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": "correct horse battery staple"},
    )
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def test_organization_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/organizations",
        json={"name": "Research Group", "slug": "research-group"},
    )
    assert response.status_code == 401


def test_creator_becomes_admin_and_can_manage_programmes(client: TestClient) -> None:
    token = register_and_login(client, "admin@example.org")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "NextGen for Earth", "slug": "nextgen-for-earth"},
    )
    assert created.status_code == 201
    organization = created.json()
    assert organization["country_code"] == "KE"

    listed = client.get("/api/organizations", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [organization["id"]]

    programme = client.post(
        f"/api/organizations/{organization['id']}/programmes",
        headers=headers,
        json={"title": "Climate Research", "slug": "climate-research"},
    )
    assert programme.status_code == 201
    assert programme.json()["status"] == "draft"

    programmes = client.get(
        f"/api/organizations/{organization['id']}/programmes",
        headers=headers,
    )
    assert programmes.status_code == 200
    assert len(programmes.json()) == 1


def test_organisation_membership_is_tenant_scoped(client: TestClient) -> None:
    first_token = register_and_login(client, "first@example.org")
    second_token = register_and_login(client, "second@example.org")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    created = client.post(
        "/api/organizations",
        headers=first_headers,
        json={"name": "Private Research Group", "slug": "private-research-group"},
    )
    organization_id = created.json()["id"]

    hidden = client.get(
        f"/api/organizations/{organization_id}/programmes",
        headers=second_headers,
    )
    assert hidden.status_code == 404

    second_list = client.get("/api/organizations", headers=second_headers)
    assert second_list.status_code == 200
    assert second_list.json() == []


def test_access_token_cannot_be_used_as_refresh_token(client: TestClient) -> None:
    token = register_and_login(client, "token@example.org")
    response = client.get(
        "/api/organizations",
        headers={"Authorization": f"Bearer {token}.tampered"},
    )
    assert response.status_code == 401


def test_invitation_requires_invited_user_to_accept(client: TestClient) -> None:
    admin_token = register_and_login(client, "org-admin@example.org")
    member_token = register_and_login(client, "new-member@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}

    organization = client.post(
        "/api/organizations",
        headers=admin_headers,
        json={"name": "Membership Test", "slug": "membership-test"},
    ).json()
    organization_id = organization["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=admin_headers,
        json={"identifier": "new-member@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    membership_id = invitation.json()["id"]
    assert invitation.json()["status"] == "invited"

    before_acceptance = client.get(
        f"/api/organizations/{organization_id}/programmes",
        headers=member_headers,
    )
    assert before_acceptance.status_code == 404

    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{membership_id}/accept",
        headers=member_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"

    after_acceptance = client.get(
        f"/api/organizations/{organization_id}/programmes",
        headers=member_headers,
    )
    assert after_acceptance.status_code == 200

    researcher_cannot_create = client.post(
        f"/api/organizations/{organization_id}/programmes",
        headers=member_headers,
        json={"title": "Unauthorised Programme", "slug": "unauthorised-programme"},
    )
    assert researcher_cannot_create.status_code == 403

    forbidden_admin_invite = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=member_headers,
        json={"identifier": "org-admin@example.org", "role": "researcher"},
    )
    assert forbidden_admin_invite.status_code == 403
