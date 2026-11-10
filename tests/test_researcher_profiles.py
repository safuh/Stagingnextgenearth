"""Integration tests for authenticated researcher profile ownership and validation."""

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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'researcher-profiles.db'}"
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


def test_researcher_can_create_and_update_only_their_own_profile(client: TestClient) -> None:
    first_headers = _register(client, "profile-owner@example.org")
    second_headers = _register(client, "profile-outsider@example.org")

    missing = client.get("/api/me/researcher-profile", headers=first_headers)
    assert missing.status_code == 404

    created = client.put(
        "/api/me/researcher-profile",
        headers=first_headers,
        json={
            "display_name": "  Dr. Researcher  ",
            "biography": "Studies rainfall variability.",
            "affiliation": "Community Climate Lab",
            "orcid": "0000-0002-1825-0097",
            "website_url": "https://example.org/research",
            "research_interests": ["Rainfall", "  Climate adaptation  "],
            "visibility": "organization",
        },
    )
    assert created.status_code == 200
    profile = created.json()
    assert profile["display_name"] == "Dr. Researcher"
    assert profile["research_interests"] == ["Rainfall", "Climate adaptation"]
    assert profile["visibility"] == "organization"
    assert "identifier" not in profile
    assert "password_hash" not in profile

    outsider_read = client.get("/api/me/researcher-profile", headers=second_headers)
    assert outsider_read.status_code == 404

    updated = client.put(
        "/api/me/researcher-profile",
        headers=first_headers,
        json={
            "display_name": "Researcher Updated",
            "research_interests": ["Hydrology"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == profile["id"]
    assert updated.json()["display_name"] == "Researcher Updated"
    assert updated.json()["research_interests"] == ["Hydrology"]


def test_researcher_profile_requires_authentication_and_valid_fields(
    client: TestClient,
) -> None:
    unauthenticated = client.put(
        "/api/me/researcher-profile",
        json={"display_name": "Unauthenticated"},
    )
    assert unauthenticated.status_code == 401

    headers = _register(client, "profile-validation@example.org")
    invalid_orcid = client.put(
        "/api/me/researcher-profile",
        headers=headers,
        json={"display_name": "Researcher", "orcid": "not-an-orcid"},
    )
    assert invalid_orcid.status_code == 422

    duplicate_interests = client.put(
        "/api/me/researcher-profile",
        headers=headers,
        json={
            "display_name": "Researcher",
            "research_interests": ["Climate", " climate "],
        },
    )
    assert duplicate_interests.status_code == 422

    invalid_website = client.put(
        "/api/me/researcher-profile",
        headers=headers,
        json={"display_name": "Researcher", "website_url": "javascript:alert(1)"},
    )
    assert invalid_website.status_code == 422


def test_orcid_cannot_be_claimed_by_two_profiles(client: TestClient) -> None:
    first_headers = _register(client, "orcid-first@example.org")
    second_headers = _register(client, "orcid-second@example.org")
    orcid = "0000-0002-1825-0097"

    first = client.put(
        "/api/me/researcher-profile",
        headers=first_headers,
        json={"display_name": "First Researcher", "orcid": orcid},
    )
    assert first.status_code == 200

    duplicate = client.put(
        "/api/me/researcher-profile",
        headers=second_headers,
        json={"display_name": "Second Researcher", "orcid": orcid},
    )
    assert duplicate.status_code == 409
