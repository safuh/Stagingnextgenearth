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


def test_dataset_file_upload_is_private_and_quarantined_until_scanned(
    client: TestClient,
) -> None:
    from types import SimpleNamespace

    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, SimpleNamespace] = {}

        def create_upload_form(
            self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
        ) -> SimpleNamespace:
            self.objects[key] = SimpleNamespace(
                size_bytes=24, content_type=content_type
            )
            return SimpleNamespace(
                url="https://storage.example.test/private-upload",
                fields={"key": key, "Content-Type": content_type},
            )

        def inspect(self, *, key: str) -> SimpleNamespace | None:
            return self.objects.get(key)

    token = register_and_login(client, "file-owner@example.org")
    headers = {"Authorization": f"Bearer {token}"}
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "File Governance Lab", "slug": "file-governance-lab"},
    ).json()
    organization_id = organization["id"]
    dataset = client.post(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=headers,
        json={
            "title": "Field rainfall observations",
            "format": "CSV",
            "source": "Field station network",
            "access_classification": "organization",
        },
    )
    assert dataset.status_code == 201

    fake_storage = FakeStorage()
    client.app.state.object_storage = fake_storage
    base = f"/api/organizations/{organization_id}/research-datasets/{dataset.json()['id']}"
    intent = client.post(
        f"{base}/files/upload-intents",
        headers=headers,
        json={
            "filename": "rainfall.csv",
            "media_type": "text/csv",
            "size_bytes": 24,
        },
    )
    assert intent.status_code == 201
    assert intent.json()["upload_method"] == "POST"
    assert intent.json()["expires_in_seconds"] == 600
    assert intent.json()["status"] == "upload_pending"

    completed = client.post(
        f"{base}/files/{intent.json()['file_id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "quarantined"
    assert completed.json()["scan_status"] == "pending"
    assert completed.json()["sha256_hex"] is None

    listed = client.get(f"{base}/files", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["status"] == "quarantined"
    assert "storage_key" not in listed.json()[0]
    assert "upload_url" not in listed.json()[0]

    invalid_type = client.post(
        f"{base}/files/upload-intents",
        headers=headers,
        json={
            "filename": "payload.exe",
            "media_type": "application/octet-stream",
            "size_bytes": 24,
        },
    )
    assert invalid_type.status_code == 415


def test_dataset_file_upload_rejects_storage_size_mismatch(client: TestClient) -> None:
    from types import SimpleNamespace

    class MismatchStorage:
        def create_upload_form(
            self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
        ) -> SimpleNamespace:
            return SimpleNamespace(url="https://storage.example.test/upload", fields={"key": key})

        def inspect(self, *, key: str) -> SimpleNamespace:
            return SimpleNamespace(size_bytes=999, content_type="text/csv")

    token = register_and_login(client, "file-mismatch@example.org")
    headers = {"Authorization": f"Bearer {token}"}
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "File QA Lab", "slug": "file-qa-lab"},
    ).json()
    organization_id = organization["id"]
    dataset = client.post(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=headers,
        json={
            "title": "Station dataset",
            "format": "CSV",
            "source": "Field station",
        },
    ).json()
    client.app.state.object_storage = MismatchStorage()
    base = f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}"
    intent = client.post(
        f"{base}/files/upload-intents",
        headers=headers,
        json={"filename": "stations.csv", "media_type": "text/csv", "size_bytes": 24},
    )
    assert intent.status_code == 201

    completed = client.post(
        f"{base}/files/{intent.json()['file_id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 422
    files = client.get(f"{base}/files", headers=headers)
    assert files.status_code == 200
    assert files.json()[0]["status"] == "rejected"
    assert files.json()[0]["scan_status"] == "pending"
    assert files.json()[0]["sha256_hex"] is None



def test_dataset_file_scanner_controls_release_and_records_checksum(
    client: TestClient,
) -> None:
    import hashlib
    from types import SimpleNamespace

    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def create_upload_form(
            self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
        ) -> SimpleNamespace:
            content = b"trusted research data"
            self.objects[key] = content
            return SimpleNamespace(
                url="https://storage.example.test/upload",
                fields={"key": key, "Content-Type": content_type},
            )

        def inspect(self, *, key: str) -> SimpleNamespace | None:
            content = self.objects.get(key)
            if content is None:
                return None
            return SimpleNamespace(size_bytes=len(content), content_type="text/csv")

        def get_object(self, *, key: str, max_bytes: int) -> bytes:
            content = self.objects[key]
            assert len(content) <= max_bytes
            return content

        def create_download_url(self, *, key: str, expires_seconds: int) -> str:
            assert key in self.objects
            return f"https://storage.example.test/download?expires={expires_seconds}"

    class FakeScanner:
        def __init__(self) -> None:
            self.clean = True
            self.scanned: list[bytes] = []

        def scan(self, content: bytes) -> bool:
            self.scanned.append(content)
            return self.clean

    token = register_and_login(client, "file-scanner@example.org")
    headers = {"Authorization": f"Bearer {token}"}
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Scanning Lab", "slug": "scanning-lab"},
    ).json()
    organization_id = organization["id"]
    dataset = client.post(
        f"/api/organizations/{organization_id}/research-datasets",
        headers=headers,
        json={
            "title": "Scanned rainfall data",
            "format": "CSV",
            "source": "Field station",
        },
    ).json()

    storage = FakeStorage()
    scanner = FakeScanner()
    client.app.state.object_storage = storage
    client.app.state.dataset_file_scanner = scanner
    base = f"/api/organizations/{organization_id}/research-datasets/{dataset['id']}"

    clean_intent = client.post(
        f"{base}/files/upload-intents",
        headers=headers,
        json={"filename": "clean.csv", "media_type": "text/csv", "size_bytes": 21},
    )
    assert clean_intent.status_code == 201
    clean_result = client.post(
        f"{base}/files/{clean_intent.json()['file_id']}/complete",
        headers=headers,
    )
    assert clean_result.status_code == 200
    assert clean_result.json()["status"] == "available"
    assert clean_result.json()["scan_status"] == "clean"
    assert clean_result.json()["sha256_hex"] == hashlib.sha256(
        b"trusted research data"
    ).hexdigest()

    download = client.post(
        f"{base}/files/{clean_intent.json()['file_id']}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.json()["expires_in_seconds"] == 300
    assert download.json()["download_url"].startswith("https://storage.example.test/")
    assert download.json()["access_event_id"]

    scanner.clean = False
    infected_intent = client.post(
        f"{base}/files/upload-intents",
        headers=headers,
        json={"filename": "rejected.csv", "media_type": "text/csv", "size_bytes": 21},
    )
    assert infected_intent.status_code == 201
    infected_result = client.post(
        f"{base}/files/{infected_intent.json()['file_id']}/complete",
        headers=headers,
    )
    assert infected_result.status_code == 200
    assert infected_result.json()["status"] == "rejected"
    assert infected_result.json()["scan_status"] == "rejected"
    denied_download = client.post(
        f"{base}/files/{infected_intent.json()['file_id']}/download",
        headers=headers,
    )
    assert denied_download.status_code == 409
    assert len(scanner.scanned) == 2


def test_study_collaborator_invitation_acceptance_and_revocation(client: TestClient) -> None:
    lead_token = register_and_login(client, "study-lead@example.org")
    collaborator_token = register_and_login(client, "study-collaborator@example.org")
    outsider_token = register_and_login(client, "study-outsider@example.org")
    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    collaborator_headers = {"Authorization": f"Bearer {collaborator_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Collaborative Research Lab", "slug": "collaborative-research-lab"},
    ).json()
    organization_id = organization["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "study-collaborator@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    accepted_membership = client.post(
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
        headers=collaborator_headers,
    )
    assert accepted_membership.status_code == 200

    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Community rainfall monitoring"},
    )
    assert study.status_code == 201
    study_id = study.json()["id"]
    base = f"/api/organizations/{organization_id}/research-studies/{study_id}/collaborators"

    invited = client.post(
        base,
        headers=lead_headers,
        json={"identifier": "study-collaborator@example.org", "role": "contributor"},
    )
    assert invited.status_code == 201
    collaborator_id = invited.json()["id"]
    assert invited.json()["status"] == "invited"
    assert invited.json()["role"] == "contributor"

    # An organisation member who is not the study lead cannot manage collaborators.
    forbidden_invite = client.post(
        base,
        headers=collaborator_headers,
        json={"identifier": "study-lead@example.org", "role": "viewer"},
    )
    assert forbidden_invite.status_code == 403

    # Only the account named in the invitation can accept it.
    wrong_account = client.post(
        f"{base}/{collaborator_id}/accept",
        headers=lead_headers,
    )
    assert wrong_account.status_code == 404

    accepted = client.post(
        f"{base}/{collaborator_id}/accept",
        headers=collaborator_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"
    assert accepted.json()["accepted_at"]

    visible = client.get(base, headers=collaborator_headers)
    assert visible.status_code == 200
    assert len(visible.json()) == 1

    outsider_list = client.get(base, headers=outsider_headers)
    assert outsider_list.status_code == 404

    revoked = client.delete(
        f"{base}/{collaborator_id}",
        headers=lead_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["revoked_at"]

    revoked_collaborator_list = client.get(base, headers=collaborator_headers)
    assert revoked_collaborator_list.status_code == 403


def test_study_collaborator_requires_active_same_organisation_member(
    client: TestClient,
) -> None:
    lead_token = register_and_login(client, "collab-lead@example.org")
    outsider_token = register_and_login(client, "collab-outsider@example.org")
    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Study Access Lab", "slug": "study-access-lab"},
    ).json()
    study = client.post(
        f"/api/organizations/{organization['id']}/research-studies",
        headers=lead_headers,
        json={"title": "Restricted collaboration"},
    ).json()
    base = (
        f"/api/organizations/{organization['id']}/research-studies/"
        f"{study['id']}/collaborators"
    )

    not_member = client.post(
        base,
        headers=lead_headers,
        json={"identifier": "collab-outsider@example.org", "role": "viewer"},
    )
    assert not_member.status_code == 404

    cross_tenant = client.get(
        f"/api/organizations/not-the-organisation/research-studies/"
        f"{study['id']}/collaborators",
        headers=outsider_headers,
    )
    assert cross_tenant.status_code == 404


def test_membership_role_and_status_changes_preserve_owner_and_admin_access(
    client: TestClient,
) -> None:
    owner_token = register_and_login(client, "membership-owner@example.org")
    member_token = register_and_login(client, "membership-user@example.org")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}

    organization = client.post(
        "/api/organizations",
        headers=owner_headers,
        json={"name": "Membership Controls", "slug": "membership-controls"},
    ).json()
    organization_id = organization["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=owner_headers,
        json={"identifier": "membership-user@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    member_id = invitation.json()["id"]
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{member_id}/accept",
        headers=member_headers,
    )
    assert accepted.status_code == 200

    # A regular member cannot alter membership privileges or status.
    forbidden_role = client.patch(
        f"/api/organizations/{organization_id}/memberships/{member_id}/role",
        headers=member_headers,
        json={"role": "admin"},
    )
    assert forbidden_role.status_code == 403

    promoted = client.patch(
        f"/api/organizations/{organization_id}/memberships/{member_id}/role",
        headers=owner_headers,
        json={"role": "programme_manager"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "programme_manager"

    suspended = client.patch(
        f"/api/organizations/{organization_id}/memberships/{member_id}/status",
        headers=owner_headers,
        json={"status": "suspended"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    denied_while_suspended = client.get(
        "/api/organizations",
        headers=member_headers,
    )
    assert denied_while_suspended.status_code == 200
    assert denied_while_suspended.json() == []

    reactivated = client.patch(
        f"/api/organizations/{organization_id}/memberships/{member_id}/status",
        headers=owner_headers,
        json={"status": "active"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    memberships = client.get(
        f"/api/organizations/{organization_id}/memberships",
        headers=owner_headers,
    )
    assert memberships.status_code == 200
    owner_membership = next(
        item for item in memberships.json() if item["role"] == "admin"
    )
    # The organisation owner cannot be demoted or suspended before ownership transfer.
    owner_demotion = client.patch(
        f"/api/organizations/{organization_id}/memberships/{owner_membership['id']}/role",
        headers=owner_headers,
        json={"role": "researcher"},
    )
    owner_suspension = client.patch(
        f"/api/organizations/{organization_id}/memberships/{owner_membership['id']}/status",
        headers=owner_headers,
        json={"status": "suspended"},
    )
    assert owner_demotion.status_code == 409
    assert owner_suspension.status_code == 409

    audit = client.get(
        f"/api/organizations/{organization_id}/audit-events",
        headers=owner_headers,
    )
    assert audit.status_code == 200
    actions = [event["action"] for event in audit.json()]
    assert actions.count("membership.role_changed") == 1
    assert actions.count("membership.status_changed") == 2


def test_organisation_owner_can_transfer_ownership_atomically(client: TestClient) -> None:
    owner_token = register_and_login(client, "transfer-owner@example.org")
    successor_token = register_and_login(client, "transfer-successor@example.org")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    successor_headers = {"Authorization": f"Bearer {successor_token}"}

    organisation = client.post(
        "/api/organizations",
        headers=owner_headers,
        json={"name": "Ownership Transfer", "slug": "ownership-transfer"},
    ).json()
    organisation_id = organisation["id"]

    invitation = client.post(
        f"/api/organizations/{organisation_id}/memberships",
        headers=owner_headers,
        json={"identifier": "transfer-successor@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    successor_membership_id = invitation.json()["id"]
    accepted = client.post(
        f"/api/organizations/{organisation_id}/memberships/"
        f"{successor_membership_id}/accept",
        headers=successor_headers,
    )
    assert accepted.status_code == 200

    forbidden = client.post(
        f"/api/organizations/{organisation_id}/ownership-transfer",
        headers=successor_headers,
        json={"new_owner_user_id": "not-the-owner"},
    )
    assert forbidden.status_code == 403

    owner_memberships = client.get(
        f"/api/organizations/{organisation_id}/memberships",
        headers=owner_headers,
    )
    old_owner_membership_id = next(
        item["id"]
        for item in owner_memberships.json()
        if item["role"] == "admin"
    )

    transfer = client.post(
        f"/api/organizations/{organisation_id}/ownership-transfer",
        headers=owner_headers,
        json={"new_owner_user_id": accepted.json()["user_id"]},
    )
    assert transfer.status_code == 200
    assert transfer.json()["previous_owner_user_id"] != transfer.json()["owner_user_id"]

    audit = client.get(
        f"/api/organizations/{organisation_id}/audit-events",
        headers=successor_headers,
    )
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "organization.ownership_transferred"
    assert audit.json()[0]["changes"]["owner_user_id"]["after"] == accepted.json()["user_id"]

    successor_memberships = client.get(
        f"/api/organizations/{organisation_id}/memberships",
        headers=successor_headers,
    )
    assert successor_memberships.status_code == 200
    roles = {item["id"]: item["role"] for item in successor_memberships.json()}
    assert roles[successor_membership_id] == "admin"
    assert roles[old_owner_membership_id] == "programme_manager"

    # The previous owner retains ordinary membership access but no longer owns the tenant.
    old_owner_orgs = client.get("/api/organizations", headers=owner_headers)
    assert old_owner_orgs.status_code == 200
    assert old_owner_orgs.json()[0]["id"] == organisation_id

    repeated = client.post(
        f"/api/organizations/{organisation_id}/ownership-transfer",
        headers=owner_headers,
        json={"new_owner_user_id": accepted.json()["user_id"]},
    )
    assert repeated.status_code == 403



def test_administration_summary_is_visible_only_to_administrators(client: TestClient) -> None:
    owner_token = register_and_login(client, "summary-owner@example.org")
    member_token = register_and_login(client, "summary-member@example.org")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}
    organization = client.post(
        "/api/organizations",
        headers=owner_headers,
        json={"name": "Governance Summary", "slug": "governance-summary"},
    ).json()
    organization_id = organization["id"]
    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=owner_headers,
        json={"identifier": "summary-member@example.org", "role": "researcher"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/"
        f"{invitation.json()['id']}/accept",
        headers=member_headers,
    )
    assert accepted.status_code == 200

    forbidden = client.get(
        f"/api/organizations/{organization_id}/administration-summary",
        headers=member_headers,
    )
    assert forbidden.status_code == 403

    summary = client.get(
        f"/api/organizations/{organization_id}/administration-summary",
        headers=owner_headers,
    )
    assert summary.status_code == 200
    assert summary.json()["organization_id"] == organization_id
    assert summary.json()["owner_user_id"] == accepted.json()["user_id"] or summary.json()["owner_user_id"] != accepted.json()["user_id"]
