# ruff: noqa: E501
"""Tests for governed public climate releases and anonymous publication boundaries."""

import asyncio
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def _auth(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    assert client.post(
        "/api/auth/register",
        json={"identifier": identifier, "password": password},
    ).status_code == 201
    response = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _release_payload() -> dict[str, object]:
    return {
        "slug": "kilifi-monthly-rainfall",
        "title": "Monthly rainfall in Kilifi",
        "summary": "Provider-derived monthly rainfall series for the Kilifi study area.",
        "provider_id": "chirps-v3",
        "data_class": "satellite_estimate",
        "geography_label": "Kilifi County, Kenya",
        "geography_resolution": "0.05° CHIRPS grid; arithmetic mean per day",
        "period_start": "2025-01-01T00:00:00+00:00",
        "period_end": "2025-12-01T00:00:00+00:00",
        "baseline": "Not applicable; descriptive annual series",
        "uncertainty_summary": "Satellite-derived estimates; not station measurements.",
        "limitations": "County aggregate does not represent every local microclimate.",
        "terms_url": "https://www.chc.ucsb.edu/data/chirps",
        "citation_url": "https://doi.org/10.15780/G2JQ0P",
        "source_ingestion_run_id": "test-ingestion-run",
    }


def test_public_climate_release_requires_independent_approval_and_publication(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'public-climate.db'}"
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )

    app = create_app(settings)
    with TestClient(app) as client:
        author = _auth(client, "climate-author@example.org")
        reviewer = _auth(client, "climate-reviewer@example.org")
        organisation = client.post(
            "/api/organizations",
            headers=author,
            json={"name": "NextGen Climate", "slug": "nextgen-climate"},
        )
        assert organisation.status_code == 201
        org_id = organisation.json()["id"]
        org_base = f"/api/organizations/{org_id}"

        # Insert a completed provider-ingestion fixture directly into the test
        # database; no external provider request or synthetic public release is used.
        run_id = str(uuid4())
        connection = sqlite3.connect(tmp_path / "public-climate.db")
        author_id = connection.execute(
            "SELECT id FROM users WHERE identifier = ?",
            ("climate-author@example.org",),
        ).fetchone()[0]
        reviewer_id = connection.execute(
            "SELECT id FROM users WHERE identifier = ?",
            ("climate-reviewer@example.org",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO climate_ingestion_runs (
                id, organization_id, provider_id, source_name, licence,
                requested_start, requested_end, requested_area, status,
                records_received, records_inserted, records_skipped,
                error_summary, started_by, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, org_id, "chirps-v3", "CHIRPS v3", "CC-BY-4.0",
                "2025-01-01T00:00:00+00:00",
                "2025-12-31T00:00:00+00:00",
                (
                    '{"west":39.7,"south":-3.7,"east":40.1,"north":-3.2,'
                    '"label":"Kilifi County, Kenya","product_variant":"sat"}'
                ),
                "completed", 2, 2, 0, None, author_id,
                "2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00",
            ),
        )
        for observed_at, value, record_id in (
            ("2025-01-01T00:00:00+00:00", 44.2, "chirps-record-1"),
            ("2025-02-01T00:00:00+00:00", 28.1, "chirps-record-2"),
        ):
            connection.execute(
                """INSERT INTO climate_observations (
                    id, organization_id, study_id, project_id, observed_at,
                    variable, value, unit, latitude, longitude, location, source,
                    ingestion_run_id, provider_id, provider_record_id, quality_status,
                    reviewed_by, reviewed_at, safeguarding_confirmed, review_note,
                    metadata_json, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid4()), org_id, None, None, observed_at,
                    "precipitation", value, "mm/month", -3.5, 39.9, None, "CHIRPS v3",
                    run_id, "chirps-v3", record_id, "verified", reviewer_id,
                    "2026-01-01T00:02:00+00:00", 0, "Provider QA reviewed", None, author_id,
                ),
            )
        connection.commit()
        connection.close()

        invitation = client.post(
            f"{org_base}/memberships",
            headers=author,
            json={"identifier": "climate-reviewer@example.org", "role": "programme_manager"},
        )
        assert invitation.status_code == 201
        accepted = client.post(
            f"{org_base}/memberships/{invitation.json()['id']}/accept",
            headers=reviewer,
        )
        assert accepted.status_code == 200
        reviewer_roles = client.patch(
            f"{org_base}/memberships/{invitation.json()['id']}/roles",
            headers=author,
            json={"roles": ["programme_manager", "executive"]},
        )
        assert reviewer_roles.status_code == 200

        run_ledger = client.get(f"{org_base}/climate-ingestion", headers=author)
        assert run_ledger.status_code == 200
        assert run_ledger.json()[0]["verified_observations"] == 2
        assert run_ledger.json()[0]["pending_observations"] == 0
        assert client.get(
            f"{org_base}/climate-public-releases", headers=author
        ).json() == []

        mismatched_area = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={**_release_payload(), "geography_label": "Busia County, Kenya"},
        )
        assert mismatched_area.status_code == 422
        mismatched_class = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={**_release_payload(), "data_class": "reanalysis"},
        )
        assert mismatched_class.status_code == 422

        created = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={
                **_release_payload(),
                "source_ingestion_run_id": run_id,
                "series_json": [{"observed_at": "2025-01-01T00:00:00Z", "value": 999999}],
                "regions_json": [{"region": "Fabricated", "value": 999999}],
            },
        )
        assert created.status_code == 201
        assert created.json()["created_by"] == author_id
        assert client.get(
            f"{org_base}/climate-public-releases", headers=author
        ).json()[0]["state"] == "draft"
        release_id = created.json()["id"]
        assert created.json()["state"] == "draft"

        public_list = client.get("/api/public/organizations/nextgen-climate/climate/releases")
        assert public_list.status_code == 200
        assert public_list.json() == []

        submitted = client.post(
            f"{org_base}/climate-public-releases/{release_id}/submit",
            headers=author,
            json={"note": "Ready for independent evidence review."},
        )
        assert submitted.status_code == 200
        assert submitted.json()["state"] == "review"

        self_approval = client.post(
            f"{org_base}/climate-public-releases/{release_id}/approve",
            headers=author,
            json={"note": "Self approval is prohibited."},
        )
        assert self_approval.status_code == 403

        approved = client.post(
            f"{org_base}/climate-public-releases/{release_id}/approve",
            headers=reviewer,
            json={"note": "Provider, licence and aggregation checked."},
        )
        assert approved.status_code == 200
        assert approved.json()["state"] == "approved"

        published = client.post(
            f"{org_base}/climate-public-releases/{release_id}/publish",
            headers=reviewer,
            json={"note": "Approved release published."},
        )
        assert published.status_code == 200
        assert published.json()["state"] == "published"

        public_detail = client.get(
            "/api/public/organizations/nextgen-climate/climate/releases/kilifi-monthly-rainfall"
        )
        assert public_detail.status_code == 200
        assert public_detail.json()["provider_id"] == "chirps-v3"
        assert public_detail.json()["data_class"] == "satellite_estimate"
        assert public_detail.json()["provider_product"] == "CHIRPS v3 SAT"
        assert public_detail.json()["license_name"] == "CC-BY-4.0"
        assert "created_by" not in public_detail.json()
        assert "source_ingestion_run_id" not in public_detail.json()

        public_series = client.get(
            "/api/public/organizations/nextgen-climate/climate/releases/"
            "kilifi-monthly-rainfall/series"
        )
        assert public_series.status_code == 200
        assert len(public_series.json()["series"]) == 2
        assert public_series.json()["regions"] == []
        assert [point["value"] for point in public_series.json()["series"]] == [44.2, 28.1]

        # A new draft version must not displace the currently published version.
        version_two = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={
                **_release_payload(),
                "title": "Monthly rainfall in Kilifi — revised",
                "source_ingestion_run_id": run_id,
            },
        )
        assert version_two.status_code == 201
        version_two_id = version_two.json()["id"]
        assert version_two.json()["version"] == 2
        assert client.get(
            "/api/public/organizations/nextgen-climate/climate/releases/"
            "kilifi-monthly-rainfall"
        ).json()["version"] == 1

        submitted_two = client.post(
            f"{org_base}/climate-public-releases/{version_two_id}/submit",
            headers=author,
            json={"note": "Revised evidence release submitted."},
        )
        assert submitted_two.status_code == 200
        approved_two = client.post(
            f"{org_base}/climate-public-releases/{version_two_id}/approve",
            headers=reviewer,
            json={"note": "Revised provider evidence independently reviewed."},
        )
        assert approved_two.status_code == 200
        published_two = client.post(
            f"{org_base}/climate-public-releases/{version_two_id}/publish",
            headers=reviewer,
            json={"note": "Publish revised version."},
        )
        assert published_two.status_code == 200
        assert published_two.json()["version"] == 2
        public_versions = client.get(
            "/api/public/organizations/nextgen-climate/climate/releases"
        ).json()
        assert len(public_versions) == 1
        assert public_versions[0]["version"] == 2
        workflow_versions = client.get(
            f"{org_base}/climate-public-releases", headers=author
        ).json()
        assert {item["version"]: item["state"] for item in workflow_versions} == {
            1: "superseded",
            2: "published",
        }

        # Public editorial insights require both a currently published climate
        # release and a separately published research publication.
        publication = client.post(
            f"{org_base}/content",
            headers=author,
            json={
                "content_type": "publication",
                "slug": "heat-maternal-health-kilifi",
                "title": "Heat and maternal health in Kilifi",
                "summary": "Published research context for climate and health.",
                "source_url": "https://example.org/research/heat-maternal-health",
            },
        )
        assert publication.status_code == 201
        publication_id = publication.json()["id"]
        assert client.patch(
            f"{org_base}/content/{publication_id}", headers=author,
            json={"publication_state": "review"},
        ).status_code == 200
        assert client.patch(
            f"{org_base}/content/{publication_id}", headers=reviewer,
            json={"publication_state": "approved"},
        ).status_code == 200
        assert client.patch(
            f"{org_base}/content/{publication_id}", headers=reviewer,
            json={"publication_state": "published"},
        ).status_code == 200

        invalid_insight = client.post(
            f"{org_base}/content",
            headers=author,
            json={
                "content_type": "climate_insight",
                "slug": "missing-evidence-links",
                "title": "Insight without evidence links",
            },
        )
        assert invalid_insight.status_code == 422

        insight = client.post(
            f"{org_base}/content",
            headers=author,
            json={
                "content_type": "climate_insight",
                "slug": "kilifi-heat-research-context",
                "title": "Reading heat exposure alongside maternal health research",
                "summary": "A contextual reading of approved climate evidence and published research.",
                "body": "The climate series describes gridded ambient conditions for its stated period and geography. It does not measure individual exposure or establish a health outcome.",
                "metadata_json": {
                    "release_slug": "kilifi-monthly-rainfall",
                    "publication_slug": "heat-maternal-health-kilifi",
                    "region": "Kilifi County, Kenya",
                    "indicator": "Precipitation",
                    "evidence_note": "Context only; no causal inference is made.",
                    "internal_review_note": "Never expose this field.",
                },
            },
        )
        assert insight.status_code == 201
        insight_id = insight.json()["id"]
        for state, actor in (("review", author), ("approved", reviewer), ("published", reviewer)):
            transition = client.patch(
                f"{org_base}/content/{insight_id}",
                headers=actor,
                json={"publication_state": state},
            )
            assert transition.status_code == 200

        public_insights = client.get(
            "/api/public/organizations/nextgen-climate/climate/insights"
        )
        assert public_insights.status_code == 200
        assert len(public_insights.json()) == 1
        assert public_insights.json()[0]["publication_title"] == "Heat and maternal health in Kilifi"
        assert public_insights.json()[0]["release_slug"] == "kilifi-monthly-rainfall"
        assert public_insights.json()[0]["publication_url"] == "https://example.org/research/heat-maternal-health"
        assert "internal_review_note" not in public_insights.json()[0]

        # A public insight with an unpublished/missing release is not exposed.
        orphan = client.post(
            f"{org_base}/content",
            headers=author,
            json={
                "content_type": "climate_insight",
                "slug": "orphan-climate-insight",
                "title": "Unlinked climate commentary",
                "summary": "This record references a release that does not exist.",
                "metadata_json": {
                    "release_slug": "not-published",
                    "publication_slug": "heat-maternal-health-kilifi",
                },
            },
        )
        assert orphan.status_code == 201
        orphan_id = orphan.json()["id"]
        for state, actor in (("review", author), ("approved", reviewer), ("published", reviewer)):
            assert client.patch(
                f"{org_base}/content/{orphan_id}",
                headers=actor,
                json={"publication_state": state},
            ).status_code == 200
        assert len(client.get(
            "/api/public/organizations/nextgen-climate/climate/insights"
        ).json()) == 1

        retracted = client.post(
            f"{org_base}/climate-public-releases/{version_two_id}/retract",
            headers=reviewer,
            json={"note": "Licence review identified a publication restriction."},
        )
        assert retracted.status_code == 200
        assert retracted.json()["state"] == "retracted"
        assert client.get(
            "/api/public/organizations/nextgen-climate/climate/releases"
        ).json() == []
        assert client.get(
            "/api/public/organizations/nextgen-climate/climate/insights"
        ).json() == []
        assert client.get(
            "/api/public/organizations/nextgen-climate/climate/releases/"
            "kilifi-monthly-rainfall"
        ).status_code == 404

        # A completed provider run is not sufficient: every inserted record
        # must have passed independent quality review before release creation.
        pending_run_id = str(uuid4())
        connection = sqlite3.connect(tmp_path / "public-climate.db")
        connection.execute(
            """INSERT INTO climate_ingestion_runs (
                id, organization_id, provider_id, source_name, licence,
                requested_start, requested_end, requested_area, status,
                records_received, records_inserted, records_skipped,
                error_summary, started_by, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pending_run_id, org_id, "chirps-v3", "CHIRPS v3", "CC-BY-4.0",
                "2025-01-01T00:00:00+00:00", "2025-12-31T00:00:00+00:00",
                (
                    '{"west":39.7,"south":-3.7,"east":40.1,"north":-3.2,'
                    '"label":"Kilifi County, Kenya","product_variant":"sat"}'
                ),
                "completed", 1, 1, 0, None, author_id,
                "2026-01-02T00:00:00+00:00", "2026-01-02T00:01:00+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO climate_observations (
                id, organization_id, study_id, project_id, observed_at,
                variable, value, unit, latitude, longitude, location, source,
                ingestion_run_id, provider_id, provider_record_id, quality_status,
                reviewed_by, reviewed_at, safeguarding_confirmed, review_note,
                metadata_json, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()), org_id, None, None, "2025-03-01T00:00:00+00:00",
                "precipitation", 31.0, "mm/month", -3.5, 39.9, None, "CHIRPS v3",
                pending_run_id, "chirps-v3", "chirps-pending-1", "pending", None,
                None, 0, None, None, author_id,
            ),
        )
        connection.commit()
        connection.close()
        blocked = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={
                **_release_payload(),
                "slug": "pending-run-must-not-publish",
                "source_ingestion_run_id": pending_run_id,
            },
        )
        assert blocked.status_code == 409

        self_quality_review = client.post(
            f"{org_base}/climate-ingestion/{pending_run_id}/review",
            headers=author,
            json={"decision": "verified", "note": "Submitter must not review own records."},
        )
        assert self_quality_review.status_code == 403

        batch_review = client.post(
            f"{org_base}/climate-ingestion/{pending_run_id}/review",
            headers=reviewer,
            json={"decision": "verified", "note": "Provider run sample and source reviewed."},
        )
        assert batch_review.status_code == 200
        assert batch_review.json()["reviewed_count"] == 1
        updated_runs = client.get(f"{org_base}/climate-ingestion", headers=reviewer)
        pending_summary = next(item for item in updated_runs.json() if item["id"] == pending_run_id)
        assert pending_summary["verified_observations"] == 1
        assert pending_summary["pending_observations"] == 0

        # A database row marked verified by its own submitter must not be
        # accepted as independent evidence for a later public release.
        connection = sqlite3.connect(tmp_path / "public-climate.db")
        connection.execute(
            "UPDATE climate_observations SET reviewed_by = created_by WHERE ingestion_run_id = ?",
            (run_id,),
        )
        connection.commit()
        connection.close()
        self_verified = client.post(
            f"{org_base}/climate-public-releases",
            headers=author,
            json={**_release_payload(), "source_ingestion_run_id": run_id},
        )
        assert self_verified.status_code == 409


def test_climate_release_rejects_invalid_period_and_unsupported_data_class() -> None:
    from pydantic import ValidationError

    from stagingnextgenearth.api.climate_public import ClimateReleaseCreate

    payload = _release_payload()
    payload["period_end"] = "2024-12-01T00:00:00+00:00"
    try:
        ClimateReleaseCreate.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("Reversed release periods must be rejected")

    payload = _release_payload()
    payload["data_class"] = "synthetic_demo"
    try:
        ClimateReleaseCreate.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("Synthetic demo data must not be a publishable data class")
