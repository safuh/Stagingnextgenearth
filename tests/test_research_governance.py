"""Integration tests for protocol versioning and independent ethics review."""

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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'research-governance.db'}"
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


def test_protocol_versions_require_independent_review_and_ethics_decision(
    client: TestClient,
) -> None:
    lead_headers = _register(client, "protocol-lead@example.org")
    reviewer_headers = _register(client, "protocol-reviewer@example.org")
    outsider_headers = _register(client, "protocol-outsider@example.org")

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Protocol Research Lab", "slug": "protocol-research-lab"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "protocol-reviewer@example.org", "role": "programme_manager"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/"
        f"{invitation.json()['id']}/accept",
        headers=reviewer_headers,
    )
    assert accepted.status_code == 200

    study_response = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Community rainfall adaptation study"},
    )
    assert study_response.status_code == 201
    study_id = study_response.json()["id"]
    base_url = (
        f"/api/organizations/{organization_id}/research-studies/{study_id}"
    )

    protocol_response = client.post(
        f"{base_url}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Rainfall adaptation protocol",
            "objectives": "Assess seasonal rainfall patterns and community adaptation.",
            "methodology": (
                "Combine station observations with structured community interviews "
                "and documented analysis."
            ),
            "sampling_and_participants": "Recruit adult community volunteers.",
            "data_management": "Store de-identified records in the approved repository.",
            "risk_and_safeguarding": "Use informed consent and a documented referral process.",
        },
    )
    assert protocol_response.status_code == 201
    protocol = protocol_response.json()
    assert protocol["version_number"] == 1
    assert protocol["status"] == "draft"
    protocol_id = protocol["id"]

    submitted = client.post(
        f"{base_url}/protocol-versions/{protocol_id}/submit",
        headers=lead_headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    lead_review = client.post(
        f"{base_url}/protocol-versions/{protocol_id}/reviews",
        headers=lead_headers,
        json={"decision": "approved", "note": "Attempted self-review is not allowed."},
    )
    assert lead_review.status_code == 403

    outsider_review = client.post(
        f"{base_url}/protocol-versions/{protocol_id}/reviews",
        headers=outsider_headers,
        json={"decision": "approved", "note": "No organisation membership."},
    )
    assert outsider_review.status_code == 404

    reviewed = client.post(
        f"{base_url}/protocol-versions/{protocol_id}/reviews",
        headers=reviewer_headers,
        json={"decision": "approved", "note": "Methods and safeguards are sufficiently documented."},
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["decision"] == "approved"

    ethics = client.post(
        f"{base_url}/ethics-reviews",
        headers=reviewer_headers,
        json={
            "protocol_version_id": protocol_id,
            "decision": "approved",
            "reference": "ERB-2026-041",
            "note": "The committee approved the submitted protocol and consent process.",
        },
    )
    assert ethics.status_code == 201
    assert ethics.json()["reference"] == "ERB-2026-041"

    protocol_history = client.get(
        f"{base_url}/protocol-versions/{protocol_id}/reviews",
        headers=lead_headers,
    )
    assert protocol_history.status_code == 200
    assert [item["decision"] for item in protocol_history.json()] == ["approved"]

    ethics_history = client.get(
        f"{base_url}/ethics-reviews",
        headers=lead_headers,
    )
    assert ethics_history.status_code == 200
    assert [item["decision"] for item in ethics_history.json()] == ["approved"]

    versions = client.get(f"{base_url}/protocol-versions", headers=lead_headers)
    assert versions.status_code == 200
    assert len(versions.json()) == 1
    assert versions.json()[0]["status"] == "approved"

    second_version = client.post(
        f"{base_url}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Rainfall adaptation protocol revision",
            "objectives": "Assess seasonal rainfall patterns and community adaptation outcomes.",
            "methodology": (
                "Combine station observations with structured community interviews "
                "and documented statistical analysis."
            ),
        },
    )
    assert second_version.status_code == 201
    assert second_version.json()["version_number"] == 2
    second_id = second_version.json()["id"]
    second_submission = client.post(
        f"{base_url}/protocol-versions/{second_id}/submit",
        headers=lead_headers,
    )
    assert second_submission.status_code == 200
    revision_decision = client.post(
        f"{base_url}/protocol-versions/{second_id}/reviews",
        headers=reviewer_headers,
        json={"decision": "revisions_required", "note": "Clarify participant recruitment."},
    )
    assert revision_decision.status_code == 201
    resubmit_same_version = client.post(
        f"{base_url}/protocol-versions/{second_id}/submit",
        headers=lead_headers,
    )
    assert resubmit_same_version.status_code == 409
    third_version = client.post(
        f"{base_url}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Rainfall adaptation protocol revised",
            "objectives": "Assess seasonal rainfall patterns and community adaptation outcomes.",
            "methodology": (
                "Combine station observations with structured community interviews "
                "and documented statistical analysis."
            ),
        },
    )
    assert third_version.status_code == 201
    assert third_version.json()["version_number"] == 3


def test_ethics_review_cannot_reference_unapproved_or_foreign_protocol(
    client: TestClient,
) -> None:
    lead_headers = _register(client, "ethics-lead@example.org")
    reviewer_headers = _register(client, "ethics-reviewer@example.org")

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Ethics Research Lab", "slug": "ethics-research-lab"},
    ).json()
    organization_id = organization["id"]
    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "ethics-reviewer@example.org", "role": "programme_manager"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/"
        f"{invitation.json()['id']}/accept",
        headers=reviewer_headers,
    )
    assert accepted.status_code == 200

    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Ethics gate study"},
    ).json()
    base_url = (
        f"/api/organizations/{organization_id}/research-studies/{study['id']}"
    )
    pending = client.post(
        f"{base_url}/ethics-reviews",
        headers=reviewer_headers,
        json={
            "protocol_version_id": "00000000-0000-0000-0000-000000000000",
            "decision": "approved",
            "note": "This protocol does not exist.",
        },
    )
    assert pending.status_code == 409
