"""Tests for the moderated organisation people directory."""

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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'people-api.db'}"
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


def register_and_login(client: TestClient, identifier: str) -> str:
    assert client.post("/api/auth/register", json={
        "identifier": identifier, "password": "correct horse battery staple"
    }).status_code == 201
    response = client.post("/api/auth/login", json={
        "identifier": identifier, "password": "correct horse battery staple"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


def test_people_directory_requires_admin_and_publication_review(client: TestClient) -> None:
    owner_token = register_and_login(client, "directory-owner@example.org")
    researcher_token = register_and_login(client, "directory-researcher@example.org")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    researcher_headers = {"Authorization": f"Bearer {researcher_token}"}
    organisation = client.post(
        "/api/organizations", headers=owner_headers,
        json={"name": "NextGen for Earth", "slug": "nextgen-for-earth"},
    ).json()
    organisation_id = organisation["id"]

    created = client.post(
        f"/api/organizations/{organisation_id}/people",
        headers=owner_headers,
        json={
            "full_name": "Example Researcher",
            "positions": ["Researcher", "Regional Ambassador"],
            "person_types": ["researcher", "ambassador"],
            "source_url": "https://nextgenforearth.org/",
        },
    )
    assert created.status_code == 201
    person = created.json()
    assert len(person["positions"]) == 2
    assert person["review_state"] == "pending"
    assert person["visibility"] == "private"

    hidden = client.get("/api/public/organizations/nextgen-for-earth/people")
    assert hidden.status_code == 200
    assert hidden.json() == []

    invitation = client.post(
        f"/api/organizations/{organisation_id}/memberships",
        headers=owner_headers,
        json={"identifier": "directory-researcher@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organisation_id}/memberships/{invitation.json()['id']}/accept",
        headers=researcher_headers,
    )
    assert accepted.status_code == 200

    forbidden = client.get(
        f"/api/organizations/{organisation_id}/people", headers=researcher_headers
    )
    assert forbidden.status_code == 403

    published = client.patch(
        f"/api/organizations/{organisation_id}/people/{person['id']}",
        headers=owner_headers,
        json={"review_state": "verified", "visibility": "public"},
    )
    assert published.status_code == 200
    public = client.get("/api/public/organizations/nextgen-for-earth/people")
    assert public.status_code == 200
    assert len(public.json()) == 1
    assert "source_url" not in public.json()[0]
    assert "created_by" not in public.json()[0]

    archived = client.patch(
        f"/api/organizations/{organisation_id}/people/{person['id']}",
        headers=owner_headers,
        json={"status": "inactive"},
    )
    assert archived.status_code == 200
    assert client.get("/api/public/organizations/nextgen-for-earth/people").json() == []


def test_people_directory_is_tenant_scoped(client: TestClient) -> None:
    first = register_and_login(client, "directory-first@example.org")
    second = register_and_login(client, "directory-second@example.org")
    first_headers = {"Authorization": f"Bearer {first}"}
    second_headers = {"Authorization": f"Bearer {second}"}
    org = client.post("/api/organizations", headers=first_headers, json={
        "name": "First Organisation", "slug": "first-organisation"
    }).json()
    response = client.get(
        f"/api/organizations/{org['id']}/people", headers=second_headers
    )
    assert response.status_code == 404
