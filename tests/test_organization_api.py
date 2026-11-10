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

    project = client.post(
        f"/api/organizations/{organization['id']}/projects",
        headers=headers,
        json={
            "title": "Western Kenya Climate Baseline",
            "programme_id": programme.json()["id"],
            "county": "Kisii",
        },
    )
    assert project.status_code == 201
    assert project.json()["status"] == "planned"
    assert project.json()["country_code"] == "KE"

    invalid_parent = client.post(
        f"/api/organizations/{organization['id']}/projects",
        headers=headers,
        json={"title": "Invalid Project", "programme_id": "not-this-tenant"},
    )
    assert invalid_parent.status_code == 404


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


def test_research_and_climate_records_are_tenant_scoped_and_provenanced(
    client: TestClient,
) -> None:
    researcher_token = register_and_login(client, "researcher@example.org")
    other_token = register_and_login(client, "outsider@example.org")
    researcher_headers = {"Authorization": f"Bearer {researcher_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    organization = client.post(
        "/api/organizations",
        headers=researcher_headers,
        json={"name": "Climate Lab", "slug": "climate-lab"},
    ).json()
    organization_id = organization["id"]

    study_response = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=researcher_headers,
        json={
            "title": "Rainfall variability in western Kenya",
            "study_type": "observational",
            "ethics_reference": "NACOSTI/TEST/001",
        },
    )
    assert study_response.status_code == 201
    study = study_response.json()
    assert study["lead_researcher_id"]
    assert study["status"] == "concept"

    observation_response = client.post(
        f"/api/organizations/{organization_id}/climate-observations",
        headers=researcher_headers,
        json={
            "observed_at": "2026-10-10T09:00:00Z",
            "variable": "precipitation",
            "value": 18.4,
            "unit": "mm",
            "latitude": -0.6773,
            "longitude": 34.7796,
            "source": "field-gauge-01",
            "study_id": study["id"],
            "metadata_json": {"method": "manual_gauge"},
        },
    )
    assert observation_response.status_code == 201
    observation = observation_response.json()
    assert observation["quality_status"] == "pending"
    assert observation["source"] == "field-gauge-01"

    listed = client.get(
        f"/api/organizations/{organization_id}/climate-observations?variable=precipitation",
        headers=researcher_headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    outsider = client.get(
        f"/api/organizations/{organization_id}/research-studies",
        headers=other_headers,
    )
    assert outsider.status_code == 404


def test_climate_observation_rejects_timezone_naive_timestamps(client: TestClient) -> None:
    token = register_and_login(client, "climate-user@example.org")
    headers = {"Authorization": f"Bearer {token}"}
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Climate QA", "slug": "climate-qa"},
    ).json()

    response = client.post(
        f"/api/organizations/{organization['id']}/climate-observations",
        headers=headers,
        json={
            "observed_at": "2026-10-10T09:00:00",
            "variable": "precipitation",
            "value": 18.4,
            "unit": "mm",
            "latitude": -0.6773,
            "longitude": 34.7796,
            "source": "field-gauge-01",
        },
    )
    assert response.status_code == 422



def test_climate_observation_requires_independent_quality_review(client: TestClient) -> None:
    admin_token = register_and_login(client, "climate-admin@example.org")
    reviewer_token = register_and_login(client, "climate-reviewer@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}

    organization = client.post(
        "/api/organizations",
        headers=admin_headers,
        json={"name": "Climate Review Lab", "slug": "climate-review-lab"},
    ).json()
    organization_id = organization["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=admin_headers,
        json={"identifier": "climate-reviewer@example.org", "role": "programme_manager"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
        headers=reviewer_headers,
    )
    assert accepted.status_code == 200

    submitted = client.post(
        f"/api/organizations/{organization_id}/climate-observations",
        headers=admin_headers,
        json={
            "observed_at": "2026-10-10T09:00:00Z",
            "variable": "precipitation",
            "value": 18.4,
            "unit": "mm",
            "latitude": -0.6773,
            "longitude": 34.7796,
            "source": "field-gauge-01",
        },
    )
    assert submitted.status_code == 201
    observation_id = submitted.json()["id"]

    self_review = client.post(
        f"/api/organizations/{organization_id}/climate-observations/{observation_id}/review",
        headers=admin_headers,
        json={"decision": "verified", "note": "Self-review must be blocked"},
    )
    assert self_review.status_code == 403

    reviewed = client.post(
        f"/api/organizations/{organization_id}/climate-observations/{observation_id}/review",
        headers=reviewer_headers,
        json={"decision": "verified", "note": "Source and measurement checked"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["quality_status"] == "verified"
    assert reviewed.json()["reviewed_by"]
    assert reviewed.json()["reviewed_at"]
    assert reviewed.json()["review_note"] == "Source and measurement checked"

    duplicate_review = client.post(
        f"/api/organizations/{organization_id}/climate-observations/{observation_id}/review",
        headers=reviewer_headers,
        json={"decision": "rejected"},
    )
    assert duplicate_review.status_code == 409

    verified = client.get(
        f"/api/organizations/{organization_id}/climate-observations?quality_status=verified",
        headers=reviewer_headers,
    )
    pending = client.get(
        f"/api/organizations/{organization_id}/climate-observations?quality_status=pending",
        headers=reviewer_headers,
    )
    assert verified.status_code == 200
    assert len(verified.json()) == 1
    assert pending.status_code == 200
    assert pending.json() == []


def test_research_dataset_registry_requires_submission_and_independent_review(
    client: TestClient,
) -> None:
    admin_token = register_and_login(client, "dataset-admin@example.org")
    researcher_token = register_and_login(client, "dataset-owner@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    researcher_headers = {"Authorization": f"Bearer {researcher_token}"}

    organization = client.post(
        "/api/organizations",
        headers=admin_headers,
        json={"name": "Dataset Governance Lab", "slug": "dataset-governance-lab"},
    ).json()
    organization_id = organization["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=admin_headers,
        json={"identifier": "dataset-owner@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
        headers=researcher_headers,
    )
    assert accepted.status_code == 200

    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=researcher_headers,
        json={"title": "Rainfall observations", "study_type": "observational"},
    )
    assert study.status_code == 201

    created = client.post(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=researcher_headers,
        json={
            "title": "Western Kenya rainfall series",
            "description": "Daily station observations",
            "version": "1.0",
            "format": "CSV",
            "source": "Field station network",
            "license": "CC-BY-4.0",
            "access_classification": "restricted",
            "study_id": study.json()["id"],
            "data_dictionary": {
                "observed_at": {"type": "datetime", "unit": "UTC"},
                "rainfall_mm": {"type": "number", "unit": "mm"},
            },
            "collection_start": "2025-01-01",
            "collection_end": "2025-12-31",
        },
    )
    assert created.status_code == 201
    dataset = created.json()
    assert dataset["status"] == "draft"
    assert dataset["owner_user_id"]

    # Restricted metadata is visible to its owner but not another tenant member.
    owner_list = client.get(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=researcher_headers,
    )
    admin_list = client.get(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=admin_headers,
    )
    assert owner_list.status_code == 200
    assert len(owner_list.json()) == 1
    assert admin_list.status_code == 200
    assert len(admin_list.json()) == 1

    submitted = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/submit",
        headers=researcher_headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"]

    # The owner cannot approve their own submission.
    self_review = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/review",
        headers=researcher_headers,
        json={"decision": "approved"},
    )
    assert self_review.status_code == 403

    rejected = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/review",
        headers=admin_headers,
        json={"decision": "rejected", "note": "Please document missing-value handling"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    null_required_field = client.patch(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}",
        headers=researcher_headers,
        json={"format": None},
    )
    assert null_required_field.status_code == 422

    blank_title = client.patch(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}",
        headers=researcher_headers,
        json={"title": "   "},
    )
    assert blank_title.status_code == 422

    corrected = client.patch(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}",
        headers=researcher_headers,
        json={
            "description": "Daily station observations with documented missing-value handling",
            "version": "1.1",
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "draft"
    assert corrected.json()["version"] == "1.1"
    assert corrected.json()["reviewed_at"] is None

    review_history = client.get(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/reviews",
        headers=researcher_headers,
    )
    assert review_history.status_code == 200
    assert len(review_history.json()) == 1
    assert review_history.json()[0]["decision"] == "rejected"
    assert review_history.json()[0]["note"] == "Please document missing-value handling"

    resubmitted = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/submit",
        headers=researcher_headers,
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "submitted"

    reviewed = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/review",
        headers=admin_headers,
        json={"decision": "approved", "note": "Corrections verified"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["reviewed_by"]
    assert reviewed.json()["reviewed_at"]
    assert reviewed.json()["review_note"] == "Corrections verified"

    review_history = client.get(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/reviews",
        headers=admin_headers,
    )
    assert review_history.status_code == 200
    assert [event["decision"] for event in review_history.json()] == ["rejected", "approved"]

    duplicate_review = client.post(
        f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}/review",
        headers=admin_headers,
        json={"decision": "rejected"},
    )
    assert duplicate_review.status_code == 409

    approved = client.get(
        f"/api/organizations/{organization_id}/research-datasets?status=approved",
        headers=admin_headers,
    )
    assert approved.status_code == 200
    assert len(approved.json()) == 1


def test_research_dataset_rejects_cross_tenant_study_and_invalid_dates(
    client: TestClient,
) -> None:
    token_a = register_and_login(client, "dataset-a@example.org")
    token_b = register_and_login(client, "dataset-b@example.org")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    org_a = client.post(
        "/api/organizations",
        headers=headers_a,
        json={"name": "Dataset Org A", "slug": "dataset-org-a"},
    ).json()
    org_b = client.post(
        "/api/organizations",
        headers=headers_b,
        json={"name": "Dataset Org B", "slug": "dataset-org-b"},
    ).json()
    study = client.post(
        f"/api/organizations/{org_b['id']}/research-studies",
        headers=headers_b,
        json={"title": "Private study"},
    )
    assert study.status_code == 201

    cross_tenant = client.post(
        f"/api/organizations/{org_a['id']}/research-datasets",
        headers=headers_a,
        json={
            "title": "Cross-tenant dataset",
            "format": "csv",
            "source": "test",
            "study_id": study.json()["id"],
        },
    )
    assert cross_tenant.status_code == 404

    invalid_dates = client.post(
        f"/api/organizations/{org_a['id']}/research-datasets",
        headers=headers_a,
        json={
            "title": "Invalid date dataset",
            "format": "csv",
            "source": "test",
            "collection_start": "2025-12-31",
            "collection_end": "2025-01-01",
        },
    )
    assert invalid_dates.status_code == 422
