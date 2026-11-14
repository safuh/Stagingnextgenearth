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

        partner = client.post(f"/api/organizations/{org_id}/partners", headers=headers, json={
            "name": "University of Nairobi", "partner_type": "university",
            "source_url": "https://nextgenforearth.org/",
        })
        assert partner.status_code == 201
        partner_id = partner.json()["id"]
        assert partner.json()["verification_state"] == "pending"
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
        assert [row["name"] for row in public_partners.json()] == ["University of Nairobi"]
        assert "verification_state" not in public_partners.json()[0]
        assert "source_url" not in public_partners.json()[0]

        entry = client.post(f"/api/organizations/{org_id}/content", headers=headers, json={
            "content_type": "programme",
            "slug": "research-capacity-building",
            "title": "Research Capacity Building",
            "summary": "Build research capability.",
            "source_url": "https://nextgenforearth.org/",
        })
        assert entry.status_code == 201
        assert entry.json()["publication_state"] == "draft"
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
        approved = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=headers,
            json={"publication_state": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["approved_by"] is not None
        published = client.patch(
            f"/api/organizations/{org_id}/content/{entry_id}",
            headers=headers,
            json={"publication_state": "published"},
        )
        assert published.status_code == 200
        public_content = client.get("/api/public/organizations/nextgen-for-earth/content")
        assert public_content.status_code == 200
        assert [row["title"] for row in public_content.json()] == ["Research Capacity Building"]
        assert "source_url" not in public_content.json()[0]
        assert "metadata_json" not in public_content.json()[0]
