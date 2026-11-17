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
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
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
    base_url = f"/api/organizations/{organization_id}/research-studies/{study_id}"

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
        json={
            "decision": "approved",
            "note": "Methods and safeguards are sufficiently documented.",
        },
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["decision"] == "approved"

    ethics = client.post(
        f"{base_url}/ethics-reviews",
        headers=reviewer_headers,
        json={
            "protocol_version_id": protocol_id,
            "decision": "approved",
            "reference": "\t=ERB-2026-041",
            "note": "The committee approved the submitted protocol and consent process.",
        },
    )
    assert ethics.status_code == 201
    assert ethics.json()["reference"] == "\t=ERB-2026-041"

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

    audit = client.get(f"/api/organizations/{organization_id}/audit-events", headers=lead_headers)
    assert audit.status_code == 200
    research_audit = [item for item in audit.json() if item["action"].startswith("research.")]
    actions = [item["action"] for item in research_audit]
    assert actions.count("research.protocol.version_created") == 3
    assert actions.count("research.protocol.submitted") == 2
    assert actions.count("research.protocol.reviewed") == 2
    assert actions.count("research.ethics.review_recorded") == 1
    assert all("note" not in item["changes"] for item in research_audit)
    assert all(item["actor_user_id"] for item in research_audit)

    governance_audit = client.get(
        f"/api/organizations/{organization_id}/research-governance/audit-events?limit=200",
        headers=lead_headers,
    )
    assert governance_audit.status_code == 200
    assert len(governance_audit.json()) == len(research_audit)
    assert all(item["action"].startswith("research.") for item in governance_audit.json())
    audit_first_page = client.get(
        f"/api/organizations/{organization_id}/research-governance/audit-events?limit=1&offset=0",
        headers=lead_headers,
    )
    audit_second_page = client.get(
        f"/api/organizations/{organization_id}/research-governance/audit-events?limit=1&offset=1",
        headers=lead_headers,
    )
    assert audit_first_page.status_code == audit_second_page.status_code == 200
    assert audit_first_page.json()[0]["id"] != audit_second_page.json()[0]["id"]
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events?offset=100001",
            headers=lead_headers,
        ).status_code
        == 422
    )
    governance_export = client.get(
        f"/api/organizations/{organization_id}/research-governance/audit-events/export",
        headers=lead_headers,
    )
    assert governance_export.status_code == 200
    assert governance_export.content.startswith(b"\xef\xbb\xbf")
    assert b"'\t=ERB-2026-041" in governance_export.content
    assert governance_export.headers["x-records-truncated"] == "false"
    truncated_export = client.get(
        f"/api/organizations/{organization_id}/research-governance/audit-events/export?limit=1",
        headers=lead_headers,
    )
    assert truncated_export.status_code == 200
    assert truncated_export.headers["x-records-truncated"] == "true"
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events/export?limit=5001",
            headers=lead_headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events/export",
            headers=reviewer_headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events/export",
            headers=outsider_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events",
            headers=reviewer_headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/organizations/{organization_id}/research-governance/audit-events",
            headers=outsider_headers,
        ).status_code
        == 404
    )

    # History endpoints are bounded and use stable newest-first/oldest-first ordering.
    first_page = client.get(f"{base_url}/protocol-versions?limit=1", headers=lead_headers)
    second_page = client.get(f"{base_url}/protocol-versions?limit=1&offset=1", headers=lead_headers)
    assert [item["version_number"] for item in first_page.json()] == [3]
    assert [item["version_number"] for item in second_page.json()] == [2]
    protocol_review_page = client.get(
        f"{base_url}/protocol-versions/{protocol_id}/reviews?limit=1&offset=0",
        headers=lead_headers,
    )
    assert [item["decision"] for item in protocol_review_page.json()] == ["approved"]
    ethics_review_page = client.get(
        f"{base_url}/ethics-reviews?limit=1&offset=0", headers=lead_headers
    )
    assert [item["decision"] for item in ethics_review_page.json()] == ["approved"]

    for invalid_query in ("limit=0", "limit=101", "offset=-1", "offset=10001"):
        assert (
            client.get(
                f"{base_url}/protocol-versions?{invalid_query}", headers=lead_headers
            ).status_code
            == 422
        )
        assert (
            client.get(
                f"{base_url}/ethics-reviews?{invalid_query}", headers=lead_headers
            ).status_code
            == 422
        )


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
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
        headers=reviewer_headers,
    )
    assert accepted.status_code == 200

    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Ethics gate study"},
    ).json()
    base_url = f"/api/organizations/{organization_id}/research-studies/{study['id']}"
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


def test_study_lifecycle_requires_protocol_ethics_and_publication_gates(
    client: TestClient,
) -> None:
    lead_headers = _register(client, "lifecycle-lead@example.org")
    reviewer_headers = _register(client, "lifecycle-reviewer@example.org")
    researcher_headers = _register(client, "lifecycle-researcher@example.org")
    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Lifecycle Research Lab", "slug": "lifecycle-research-lab"},
    ).json()
    organization_id = organization["id"]
    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "lifecycle-reviewer@example.org", "role": "programme_manager"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
        headers=reviewer_headers,
    )
    assert accepted.status_code == 200
    researcher_invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "lifecycle-researcher@example.org", "role": "researcher"},
    )
    assert researcher_invitation.status_code == 201
    researcher_accepted = client.post(
        f"/api/organizations/{organization_id}/memberships/"
        f"{researcher_invitation.json()['id']}/accept",
        headers=researcher_headers,
    )
    assert researcher_accepted.status_code == 200

    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Lifecycle gate study"},
    ).json()
    study_id = study["id"]
    base = f"/api/organizations/{organization_id}/research-studies/{study_id}"
    status_url = f"{base}/status"

    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "protocol"}).status_code
        == 409
    )
    protocol = client.post(
        f"{base}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Lifecycle protocol",
            "objectives": "Evaluate the effect of seasonal rainfall variability.",
            "methodology": "Use calibrated observations and documented statistical methods.",
        },
    )
    assert protocol.status_code == 201
    protocol_id = protocol.json()["id"]
    assert (
        client.post(
            f"{base}/protocol-versions/{protocol_id}/submit", headers=lead_headers
        ).status_code
        == 200
    )
    review = client.post(
        f"{base}/protocol-versions/{protocol_id}/reviews",
        headers=reviewer_headers,
        json={"decision": "approved", "note": "Protocol methods and safeguards are adequate."},
    )
    assert review.status_code == 201
    moved_to_protocol = client.patch(status_url, headers=lead_headers, json={"status": "protocol"})
    assert moved_to_protocol.status_code == 200
    assert moved_to_protocol.json()["status"] == "protocol"

    # Approval of a protocol alone is not sufficient to begin field activity.
    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "active"}).status_code == 409
    )
    ethics = client.post(
        f"{base}/ethics-reviews",
        headers=reviewer_headers,
        json={
            "protocol_version_id": protocol_id,
            "decision": "approved",
            "reference": "ERB-LIFECYCLE-01",
            "note": "Participant consent and data safeguards are approved.",
        },
    )
    assert ethics.status_code == 201
    activated = client.patch(status_url, headers=lead_headers, json={"status": "active"})
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    # An amendment pauses an active study and requires independent approval plus
    # an ethics decision for the new version, not the previously approved version.
    amendment = client.post(
        f"{base}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Lifecycle protocol amendment",
            "objectives": "Extend evaluation to include additional seasonal observations.",
            "methodology": (
                "Add documented quality checks and a pre-registered sensitivity analysis."
            ),
        },
    )
    assert amendment.status_code == 201
    amendment_id = amendment.json()["id"]
    paused = client.get(
        f"/api/organizations/{organization_id}/research-studies", headers=lead_headers
    )
    assert paused.status_code == 200
    assert next(item for item in paused.json() if item["id"] == study_id)["status"] == "protocol"
    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "active"}).status_code == 409
    )
    assert (
        client.post(
            f"{base}/protocol-versions/{amendment_id}/submit", headers=lead_headers
        ).status_code
        == 200
    )
    amendment_review = client.post(
        f"{base}/protocol-versions/{amendment_id}/reviews",
        headers=reviewer_headers,
        json={"decision": "approved", "note": "The amended methods and safeguards are acceptable."},
    )
    assert amendment_review.status_code == 201
    # The first version's ethics approval cannot authorise the amended protocol.
    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "active"}).status_code == 409
    )
    amendment_ethics = client.post(
        f"{base}/ethics-reviews",
        headers=reviewer_headers,
        json={
            "protocol_version_id": amendment_id,
            "decision": "approved",
            "reference": "ERB-LIFECYCLE-02",
            "note": "The amended participant and data safeguards are approved.",
        },
    )
    assert amendment_ethics.status_code == 201
    reactivated = client.patch(status_url, headers=lead_headers, json={"status": "active"})
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    completed = client.patch(status_url, headers=lead_headers, json={"status": "completed"})
    assert completed.status_code == 200
    completed_amendment = client.post(
        f"{base}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Post-completion amendment",
            "objectives": "Attempt to amend a completed study record.",
            "methodology": "This amendment should not be accepted after completion.",
        },
    )
    assert completed_amendment.status_code == 409
    # A completed study cannot be marked published without a linked publication record.
    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "published"}).status_code
        == 409
    )
    publication = client.post(
        f"{base}/publications",
        headers=lead_headers,
        json={
            "title": "Seasonal rainfall variability findings",
            "authors": ["Research Team"],
            "publication_type": "report",
        },
    )
    assert publication.status_code == 201
    published = client.patch(status_url, headers=lead_headers, json={"status": "published"})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    published_amendment = client.post(
        f"{base}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Post-publication amendment",
            "objectives": "Attempt to amend a published study record.",
            "methodology": "This amendment should not be accepted after publication.",
        },
    )
    assert published_amendment.status_code == 409
    archived = client.patch(status_url, headers=lead_headers, json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert (
        client.patch(status_url, headers=lead_headers, json={"status": "active"}).status_code == 409
    )
    finalised_amendment = client.post(
        f"{base}/protocol-versions",
        headers=lead_headers,
        json={
            "title": "Post-archive amendment",
            "objectives": "Attempt to amend a finalised study record.",
            "methodology": "This amendment should not be accepted after archival.",
        },
    )
    assert finalised_amendment.status_code == 409

    # A non-manager researcher cannot alter the organisation's study lifecycle.
    assert (
        client.patch(status_url, headers=researcher_headers, json={"status": "active"}).status_code
        == 403
    )

    audit_events = client.get(
        f"/api/organizations/{organization_id}/audit-events", headers=lead_headers
    )
    assert audit_events.status_code == 200
    lifecycle_events = [
        event for event in audit_events.json() if event["action"] == "research.study.status_changed"
    ]
    assert len(lifecycle_events) == 7
    assert lifecycle_events[0]["changes"] == {
        "study_id": study_id,
        "from_status": "published",
        "to_status": "archived",
    }
    amendment_pause = next(
        event
        for event in lifecycle_events
        if event["changes"].get("reason") == "protocol_amendment_requires_reapproval"
    )
    assert amendment_pause["changes"]["from_status"] == "active"
    assert amendment_pause["changes"]["to_status"] == "protocol"
    assert amendment_pause["changes"]["protocol_version_id"] == amendment_id
