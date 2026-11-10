"""Tests for the study publication registry and identifier validation."""

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
    database_url = "sqlite+aiosqlite:///" + str(tmp_path / "publications.db")
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


def test_publication_registry_and_external_identifiers(client: TestClient) -> None:
    headers = _register(client, "publication-author@example.org")
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Publication Lab", "slug": "publication-lab"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]
    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=headers,
        json={"title": "Urban tree restoration outcomes"},
    )
    assert study.status_code == 201
    study_id = study.json()["id"]
    base = (
        f"/api/organizations/{organization_id}/research-studies/{study_id}/publications"
    )

    invalid = client.post(
        base,
        headers=headers,
        json={
            "title": "Invalid DOI record",
            "authors": ["A. Researcher"],
            "publication_type": "article",
            "doi": "not-a-doi",
        },
    )
    assert invalid.status_code == 422

    created = client.post(
        base,
        headers=headers,
        json={
            "title": "Urban canopy recovery after community restoration",
            "authors": ["A. Researcher", "B. Scientist"],
            "author_orcids": ["https://orcid.org/0000-0002-1825-0097"],
            "publication_type": "article",
            "journal_or_venue": "Journal of Urban Ecology",
            "published_on": "2026-05-20",
            "doi": "https://doi.org/10.1234/Example.2026.01",
            "openalex_id": "https://openalex.org/W1234567890",
            "url": "https://example.org/publication",
            "abstract": "A study of urban canopy recovery.",
        },
    )
    assert created.status_code == 201
    publication = created.json()
    assert publication["doi"] == "10.1234/example.2026.01"
    assert publication["author_orcids"] == ["0000-0002-1825-0097"]
    assert publication["openalex_id"] == "W1234567890"
    assert publication["authors"] == ["A. Researcher", "B. Scientist"]

    listed = client.get(base, headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [publication["id"]]

    duplicate = client.post(
        base,
        headers=headers,
        json={
            "title": "Duplicate DOI record",
            "authors": ["A. Researcher"],
            "publication_type": "article",
            "doi": "10.1234/EXAMPLE.2026.01",
        },
    )
    assert duplicate.status_code == 409


def test_publication_identifiers_are_validated(client: TestClient) -> None:
    headers = _register(client, "publication-validation@example.org")
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Identifier Lab", "slug": "identifier-lab"},
    ).json()
    study = client.post(
        f"/api/organizations/{organization['id']}/research-studies",
        headers=headers,
        json={"title": "Identifier validation study"},
    ).json()
    base = (
        f"/api/organizations/{organization['id']}/research-studies/{study['id']}/publications"
    )
    for payload in (
        {"author_orcids": ["not-an-orcid"]},
        {"author_orcids": ["0000-0002-1825-0098"]},
        {"openalex_id": "A123"},
        {"url": "javascript:alert(1)"},
        {"url": "https://user:password@example.org/publication"},
        {"title": "   "},
    ):
        response = client.post(
            base,
            headers=headers,
            json={
                "title": "Identifier validation publication",
                "authors": ["A. Researcher"],
                "publication_type": "report",
                **payload,
            },
        )
        assert response.status_code == 422


def test_publication_access_is_limited_to_active_study_collaborators(
    client: TestClient,
) -> None:
    lead_headers = _register(client, "publication-lead@example.org")
    viewer_headers = _register(client, "publication-viewer@example.org")
    member_headers = _register(client, "publication-member@example.org")
    outsider_headers = _register(client, "publication-outsider@example.org")

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Publication Access Lab", "slug": "publication-access-lab"},
    ).json()
    organization_id = organization["id"]
    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Community biodiversity survey"},
    ).json()
    study_id = study["id"]
    base = (
        f"/api/organizations/{organization_id}/research-studies/{study_id}/publications"
    )

    for headers, identifier in (
        (viewer_headers, "publication-viewer@example.org"),
        (member_headers, "publication-member@example.org"),
    ):
        invitation = client.post(
            f"/api/organizations/{organization_id}/memberships",
            headers=lead_headers,
            json={"identifier": identifier, "role": "youth_volunteer"},
        )
        assert invitation.status_code == 201
        accepted = client.post(
            f"/api/organizations/{organization_id}/memberships/"
            f"{invitation.json()['id']}/accept",
            headers=headers,
        )
        assert accepted.status_code == 200

    invitation = client.post(
        f"/api/organizations/{organization_id}/research-studies/{study_id}/collaborators",
        headers=lead_headers,
        json={"identifier": "publication-viewer@example.org", "role": "viewer"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/research-studies/{study_id}/"
        f"collaborators/{invitation.json()['id']}/accept",
        headers=viewer_headers,
    )
    assert accepted.status_code == 200

    payload = {
        "title": "Biodiversity observations in community-managed forests",
        "authors": ["A. Researcher"],
        "publication_type": "report",
    }
    assert client.get(base, headers=viewer_headers).status_code == 200
    assert client.post(base, headers=viewer_headers, json=payload).status_code == 403

    assert client.get(base, headers=member_headers).status_code == 403
    assert client.post(base, headers=member_headers, json=payload).status_code == 403
    assert client.get(base, headers=outsider_headers).status_code == 403

    created = client.post(base, headers=lead_headers, json=payload)
    assert created.status_code == 201
    assert client.get(base, headers=viewer_headers).json()[0]["id"] == created.json()["id"]
