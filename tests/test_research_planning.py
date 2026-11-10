"""Tests for research proposal governance and milestone tracking."""

from datetime import date

from fastapi.testclient import TestClient

from .test_research_governance import _register


def test_proposal_review_and_milestone_lifecycle(client: TestClient) -> None:
    lead_headers = _register(client, "planning-lead@example.org")
    reviewer_headers = _register(client, "planning-reviewer@example.org")
    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Planning Research Lab", "slug": "planning-research-lab"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]

    invitation = client.post(
        f"/api/organizations/{organization_id}/memberships",
        headers=lead_headers,
        json={"identifier": "planning-reviewer@example.org", "role": "programme_manager"},
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
        json={"title": "Community restoration study"},
    ).json()
    base = f"/api/organizations/{organization_id}/research-studies/{study['id']}"

    proposal_response = client.post(
        f"{base}/proposals",
        headers=lead_headers,
        json={
            "title": "Restoration field study",
            "rationale": "Document restoration outcomes across participating communities.",
            "objectives": "Measure ecological recovery and community participation outcomes.",
            "proposed_methods": "Use repeat field observations and structured community interviews.",
            "expected_outcomes": "A reproducible baseline and follow-up dataset.",
        },
    )
    assert proposal_response.status_code == 201
    proposal = proposal_response.json()
    assert proposal["status"] == "draft"

    submitted = client.post(
        f"{base}/proposals/{proposal['id']}/submit",
        headers=lead_headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    self_review = client.post(
        f"{base}/proposals/{proposal['id']}/reviews",
        headers=lead_headers,
        json={"decision": "approved", "note": "This self-review must be rejected."},
    )
    assert self_review.status_code == 403

    reviewed = client.post(
        f"{base}/proposals/{proposal['id']}/reviews",
        headers=reviewer_headers,
        json={
            "decision": "revisions_required",
            "note": "Clarify the sampling frame and field observation schedule.",
        },
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["decision"] == "revisions_required"
    history = client.get(
        f"{base}/proposals/{proposal['id']}/reviews",
        headers=lead_headers,
    )
    assert history.status_code == 200
    assert len(history.json()) == 1

    milestone = client.post(
        f"{base}/milestones",
        headers=lead_headers,
        json={
            "title": "Complete baseline field survey",
            "description": "Collect and quality-check the initial field observations.",
            "assigned_to": invitation.json()["user_id"] if "user_id" in invitation.json() else None,
            "due_date": date(2027, 3, 31).isoformat(),
        },
    )
    # Membership invitation responses intentionally do not expose account identifiers.
    assert milestone.status_code == 201
    milestone_id = milestone.json()["id"]
    updated = client.patch(
        f"{base}/milestones/{milestone_id}",
        headers=lead_headers,
        json={"status": "in_progress", "progress_percent": 60},
    )
    assert updated.status_code == 200
    assert updated.json()["progress_percent"] == 60
    completed = client.patch(
        f"{base}/milestones/{milestone_id}",
        headers=lead_headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["progress_percent"] == 100
