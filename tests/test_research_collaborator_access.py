"""Integration coverage for study collaborator authorization on dataset files."""

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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'collaborators.db'}"
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


def test_active_study_collaborator_can_read_restricted_dataset_file_metadata(
    client: TestClient,
) -> None:
    admin_headers = _register(client, "study-lead@example.org")
    viewer_headers = _register(client, "study-viewer@example.org")
    outsider_headers = _register(client, "study-outsider@example.org")

    organization = client.post(
        "/api/organizations",
        headers=admin_headers,
        json={"name": "Research Lab", "slug": "research-lab"},
    ).json()
    organization_id = organization["id"]
    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=admin_headers,
        json={"title": "Rainfall monitoring study"},
    ).json()
    dataset = client.post(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=admin_headers,
        json={
            "title": "Restricted rainfall observations",
            "format": "csv",
            "source": "field monitoring",
            "access_classification": "restricted",
            "study_id": study["id"],
        },
    )
    assert dataset.status_code == 201
    dataset_id = dataset.json()["id"]

    for headers, identifier in (
        (viewer_headers, "study-viewer@example.org"),
        (outsider_headers, "study-outsider@example.org"),
    ):
        invitation = client.post(
            f"/api/organizations/{organization_id}/memberships",
            headers=admin_headers,
            json={"identifier": identifier, "role": "youth_volunteer"},
        )
        assert invitation.status_code == 201
        accepted = client.post(
            f"/api/organizations/{organization_id}/memberships/"
            f"{invitation.json()['id']}/accept",
            headers=headers,
        )
        assert accepted.status_code == 200

    collaborator = client.post(
        f"/api/organizations/{organization_id}/research-studies/{study['id']}/collaborators",
        headers=admin_headers,
        json={"identifier": "study-viewer@example.org", "role": "viewer"},
    )
    assert collaborator.status_code == 201
    accepted_collaboration = client.post(
        f"/api/organizations/{organization_id}/research-studies/{study['id']}/"
        f"collaborators/{collaborator.json()['id']}/accept",
        headers=viewer_headers,
    )
    assert accepted_collaboration.status_code == 200
    assert accepted_collaboration.json()["status"] == "active"

    files_url = (
        f"/api/organizations/{organization_id}/research-datasets/{dataset_id}/files"
    )
    allowed = client.get(files_url, headers=viewer_headers)
    assert allowed.status_code == 200
    assert allowed.json() == []

    denied = client.get(files_url, headers=outsider_headers)
    assert denied.status_code == 403
