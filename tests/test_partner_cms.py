"""Partner registry and public CMS moderation tests."""
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def test_partner_and_cms_publication_workflows(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'partners-cms.db'}"
    engine = create_async_engine(database_url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )
    with TestClient(create_app(settings)) as client:
        client.post("/api/auth/register", json={
            "identifier": "partner-admin@example.org",
            "password": "correct horse battery staple",
        })
        login = client.post("/api/auth/login", json={
            "identifier": "partner-admin@example.org",
            "password": "correct horse battery staple",
        })
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        org = client.post("/api/organizations", headers=headers, json={
            "name": "NextGen for Earth", "slug": "nextgen-for-earth",
        }).json()
        org_id = org["id"]

        # A secondary administrator grant must be honoured by partner routes.
        client.post("/api/auth/register", json={
            "identifier": "partner-executive@example.org",
            "password": "correct horse battery staple",
        })
        invited_executive = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=headers,
            json={"identifier": "partner-executive@example.org", "role": "employee"},
        )
        assert invited_executive.status_code == 201
        executive_login = client.post("/api/auth/login", json={
            "identifier": "partner-executive@example.org",
            "password": "correct horse battery staple",
        })
        executive_headers = {
            "Authorization": "Bearer " + executive_login.json()["access_token"]
        }
        accepted_executive = client.post(
            f"/api/organizations/{org_id}/memberships/{invited_executive.json()['id']}/accept",
            headers=executive_headers,
        )
        assert accepted_executive.status_code == 200
        assigned_roles = client.patch(
            f"/api/organizations/{org_id}/memberships/{invited_executive.json()['id']}/roles",
            headers=headers,
            json={"roles": ["employee", "executive"]},
        )
        assert assigned_roles.status_code == 200
        secondary_admin_partner = client.post(
            f"/api/organizations/{org_id}/partners",
            headers=executive_headers,
            json={"name": "Secondary Role Partner", "partner_type": "ngo"},
        )
        assert secondary_admin_partner.status_code == 201

        partner = client.post(f"/api/organizations/{org_id}/partners", headers=headers, json={
            "name": "University of Nairobi", "partner_type": "university",
            "source_url": "https://nextgenforearth.org/",
        })
        assert partner.status_code == 201
        partner_id = partner.json()["id"]
        assert partner.json()["verification_state"] == "pending"

        # Partner contact details are private and permission starts disabled.
        contact = client.post(
            f"/api/organizations/{org_id}/partners/{partner_id}/contacts",
            headers=headers,
            json={"full_name": "Partnership Liaison", "job_title": "Research Coordinator",
                  "email": "LIAISON@university.example", "phone": "+254700000000"},
        )
        assert contact.status_code == 201
        contact_id = contact.json()["id"]
        assert contact.json()["contact_permission"] is False
        contacts = client.get(
            f"/api/organizations/{org_id}/partners/{partner_id}/contacts",
            headers=headers,
        )
        assert contacts.status_code == 200
        assert contacts.json()[0]["email"] == "liaison@university.example"
        permission = client.patch(
            f"/api/organizations/{org_id}/partners/{partner_id}/contacts/{contact_id}",
            headers=headers, json={"contact_permission": True},
        )
        assert permission.status_code == 200
        assert permission.json()["contact_permission"] is True
        assert permission.json()["permission_recorded_at"] is not None
        deactivated = client.patch(
            f"/api/organizations/{org_id}/partners/{partner_id}/contacts/{contact_id}",
            headers=headers, json={"status": "inactive"},
        )
        assert deactivated.status_code == 200
        assert client.get(
            f"/api/organizations/{org_id}/partners/{partner_id}/contacts",
            headers=headers,
        ).json() == []
        partner_audit = client.get(
            f"/api/organizations/{org_id}/partners/{partner_id}/audit-events",
            headers=headers,
        )
        assert partner_audit.status_code == 200
        assert any(event["action"] == "record.created" for event in partner_audit.json())
        assert client.get("/api/public/organizations/nextgen-for-earth/partners").json() == []

        programme = client.post(f"/api/organizations/{org_id}/programmes", headers=headers, json={
            "title": "Research Capacity Building", "slug": "research-capacity-building",
        })
        assert programme.status_code == 201
        linked = client.post(
            f"/api/organizations/{org_id}/partners/{partner_id}/programmes",
            headers=headers,
            json={"programme_id": programme.json()["id"], "partner_role": "research_partner"},
        )
        assert linked.status_code == 201

        verified = client.patch(
            f"/api/organizations/{org_id}/partners/{partner_id}",
            headers=headers,
            json={
                "verification_state": "verified",
                "relationship_status": "active",
                "visibility": "public",
            },
        )
        assert verified.status_code == 200
        public_partners = client.get("/api/public/organizations/nextgen-for-earth/partners")
        assert public_partners.status_code == 200
        partner_audit = client.get(
            f"/api/organizations/{org_id}/partners/{partner_id}/audit-events",
            headers=headers,
        )
        assert partner_audit.status_code == 200
        state_change = next(
            event for event in partner_audit.json()
            if event["action"] == "record.state_changed"
        )
        assert "verification_state" in state_change["changed_fields"]
        assert [row["name"] for row in public_partners.json()] == ["University of Nairobi"]
        assert "verification_state" not in public_partners.json()[0]
        assert "source_url" not in public_partners.json()[0]

        client.post("/api/auth/register", json={
            "identifier": "cms-contributor@example.org",
            "password": "correct horse battery staple",
        })
        contributor_invite = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=headers,
            json={"identifier": "cms-contributor@example.org", "role": "employee"},
        )
        assert contributor_invite.status_code == 201
        contributor_login = client.post("/api/auth/login", json={
            "identifier": "cms-contributor@example.org",
            "password": "correct horse battery staple",
        })
        contributor_headers = {
            "Authorization": "Bearer " + contributor_login.json()["access_token"]
        }
        accepted_contributor = client.post(
            f"/api/organizations/{org_id}/memberships/{contributor_invite.json()['id']}/accept",
            headers=contributor_headers,
        )
        assert accepted_contributor.status_code == 200
        contributor_entry = client.post(
            f"/api/organizations/{org_id}/content",
            headers=contributor_headers,
            json={
                "content_type": "research_area",
                "slug": "community-climate-research",
                "title": "Community Climate Research",
                "summary": "A contributor-authored draft.",
            },
        )
        assert contributor_entry.status_code == 201
        contributor_id = contributor_entry.json()["id"]
        own_records = client.get(
            f"/api/organizations/{org_id}/content", headers=contributor_headers
        )
        assert [record["id"] for record in own_records.json()] == [contributor_id]
        denied_transition = client.patch(
            f"/api/organizations/{org_id}/content/{contributor_id}",
            headers=contributor_headers,
            json={"publication_state": "approved"},
        )
        assert denied_transition.status_code == 403
        submitted = client.patch(
            f"/api/organizations/{org_id}/content/{contributor_id}",
            headers=contributor_headers,
            json={"publication_state": "review"},
        )
        assert submitted.status_code == 200
        assert submitted.json()["publication_state"] == "review"
        locked_submission = client.patch(
            f"/api/organizations/{org_id}/content/{contributor_id}",
            headers=contributor_headers,
            json={"title": "Attempt to edit submitted content"},
        )
        assert locked_submission.status_code == 409
        assert client.get(
            f"/api/organizations/{org_id}/content/{contributor_id}/audit-events",
            headers=contributor_headers,
        ).status_code == 403

        entry = client.post(f"/api/organizations/{org_id}/content", headers=headers, json={
            "content_type": "programme",
            "slug": "research-capacity-building",
            "title": "Research Capacity Building",
            "summary": "Build research capability.",
            "source_url": "https://nextgenforearth.org/",
        })
        assert entry.status_code == 201
        assert entry.json()["publication_state"] == "draft"
        content_audit = client.get(
            f"/api/organizations/{org_id}/content/{entry.json()['id']}/audit-events",
            headers=headers,
        )
        assert content_audit.status_code == 200
        assert content_audit.json()[0]["action"] == "record.created"
        assert client.get("/api/public/organizations/nextgen-for-earth/content").json() == []

        entry_id = entry.json()["id"]
        direct_publish = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=headers,
            json={"publication_state": "published"},
        )
        assert direct_publish.status_code == 409
        review = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=headers,
            json={"publication_state": "review"},
        )
        assert review.status_code == 200

        # The author cannot approve their own content. An independent executive
        # reviewer must accept the invitation before approving or publishing.
        self_approval = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=headers,
            json={"publication_state": "approved"},
        )
        assert self_approval.status_code == 403
        client.post("/api/auth/register", json={
            "identifier": "cms-reviewer@example.org",
            "password": "correct horse battery staple",
        })
        invited = client.post(
            f"/api/organizations/{org_id}/memberships",
            headers=headers,
            json={"identifier": "cms-reviewer@example.org", "role": "executive"},
        )
        assert invited.status_code == 201
        reviewer_login = client.post("/api/auth/login", json={
            "identifier": "cms-reviewer@example.org",
            "password": "correct horse battery staple",
        })
        reviewer_headers = {
            "Authorization": "Bearer " + reviewer_login.json()["access_token"]
        }
        accepted = client.post(
            f"/api/organizations/{org_id}/memberships/{invited.json()['id']}/accept",
            headers=reviewer_headers,
        )
        assert accepted.status_code == 200

        approved = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=reviewer_headers,
            json={"publication_state": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["approved_by"] is not None
        published = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=reviewer_headers,
            json={"publication_state": "published"},
        )
        assert published.status_code == 200
        public_content = client.get("/api/public/organizations/nextgen-for-earth/content")
        assert public_content.status_code == 200
        assert [row["title"] for row in public_content.json()] == ["Research Capacity Building"]
        assert "source_url" not in public_content.json()[0]
        assert "metadata_json" not in public_content.json()[0]

        publication = client.post(
            f"/api/organizations/{org_id}/content",
            headers=headers,
            json={
                "content_type": "publication",
                "slug": "heat-health-publication",
                "title": "Heat, health and community resilience",
                "summary": "A. Researcher et al. · Example Journal",
                "metadata_json": {
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "source_capture": "https://internal.example/capture",
                },
                "source_url": "https://doi.org/10.0000/example",
            },
        )
        assert publication.status_code == 201
        for state in ("review",):
            moved = client.patch(
                f"/api/organizations/{org_id}/content/{publication.json()['id']}",
                headers=headers,
                json={"publication_state": state},
            )
            assert moved.status_code == 200
        publication_approved = client.patch(
            f"/api/organizations/{org_id}/content/{publication.json()['id']}",
            headers=reviewer_headers,
            json={"publication_state": "approved"},
        )
        assert publication_approved.status_code == 200
        publication_published = client.patch(
            f"/api/organizations/{org_id}/content/{publication.json()['id']}",
            headers=reviewer_headers,
            json={"publication_state": "published"},
        )
        assert publication_published.status_code == 200
        public_rows = client.get(
            "/api/public/organizations/nextgen-for-earth/content"
        ).json()
        public_publication = next(
            row for row in public_rows if row["content_type"] == "publication"
        )
        assert public_publication["source_url"] == "https://doi.org/10.0000/example"
        assert public_publication["metadata_json"] == {
            "authors": ["A. Researcher"],
            "year": 2025,
        }

        # Editing already-published material immediately withdraws it and
        # invalidates the prior approval so stale text cannot remain public.
        edited = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=reviewer_headers,
            json={"summary": "Updated summary awaiting review."},
        )
        assert edited.status_code == 200
        assert edited.json()["publication_state"] == "draft"
        assert edited.json()["approved_by"] is None
        assert edited.json()["approved_at"] is None
        remaining_public = client.get(
            "/api/public/organizations/nextgen-for-earth/content"
        ).json()
        assert [row["slug"] for row in remaining_public] == ["heat-health-publication"]
