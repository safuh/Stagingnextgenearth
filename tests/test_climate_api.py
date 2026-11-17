"""HTTP tests for tenant-scoped climate quality summaries."""

import asyncio
from pathlib import Path

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


def test_climate_quality_summary_is_tenant_scoped_and_time_bounded(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-quality-api.db'}"
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
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "climate-quality-owner@example.org")
        other = _auth(client, "climate-quality-other@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate QA", "slug": "climate-qa"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/climate-observations"

        for observed_at, variable, value, unit in (
            ("2026-01-05T00:00:00+00:00", "precipitation", 12.0, "mm"),
            ("2026-01-15T00:00:00+00:00", "air_temperature_2m", 25.0, "degC"),
        ):
            created = client.post(
                base,
                headers=owner,
                json={
                    "observed_at": observed_at,
                    "variable": variable,
                    "value": value,
                    "unit": unit,
                    "latitude": -1.286,
                    "longitude": 36.817,
                    "source": "manual field observation",
                },
            )
            assert created.status_code == 201

        summary = client.get(f"{base}/quality-summary", headers=owner)
        assert summary.status_code == 200
        assert summary.json() == {
            "total": 2,
            "by_status": {"pending": 2},
            "by_variable": {"air_temperature_2m": 1, "precipitation": 1},
        }

        bounded = client.get(
            f"{base}/quality-summary",
            headers=owner,
            params={
                "start": "2026-01-10T00:00:00+00:00",
                "end": "2026-02-01T00:00:00+00:00",
            },
        )
        assert bounded.status_code == 200
        assert bounded.json()["total"] == 1
        assert bounded.json()["by_variable"] == {"air_temperature_2m": 1}

        invalid = client.get(
            f"{base}/quality-summary",
            headers=owner,
            params={
                "start": "2026-02-01T00:00:00+00:00",
                "end": "2026-01-01T00:00:00+00:00",
            },
        )
        assert invalid.status_code == 422

        # Conceal tenant resources from non-members to avoid organization
        # enumeration; this is the established authorization contract.
        assert client.get(
            f"/api/organizations/{organization_id}/climate-observations/quality-summary",
            headers=other,
        ).status_code == 404


def test_climate_observation_review_writes_immutable_audit_history(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'climate-review-audit.db'}"
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
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "climate-review-owner@example.org")
        reviewer = _auth(client, "climate-reviewer@example.org")
        organisation = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "Climate Review Audit", "slug": "climate-review-audit"},
        )
        assert organisation.status_code == 201
        organization_id = organisation.json()["id"]
        base = f"/api/organizations/{organization_id}"
        invited = client.post(
            f"{base}/memberships",
            headers=owner,
            json={"identifier": "climate-reviewer@example.org", "role": "programme_manager"},
        )
        assert invited.status_code == 201
        accepted = client.post(
            f"{base}/memberships/{invited.json()['id']}/accept",
            headers=reviewer,
        )
        assert accepted.status_code == 200

        created = client.post(
            f"{base}/climate-observations",
            headers=owner,
            json={
                "observed_at": "2026-02-01T09:00:00+00:00",
                "variable": "precipitation",
                "value": 18.5,
                "unit": "mm",
                "latitude": -1.286,
                "longitude": 36.817,
                "source": "community rain gauge",
            },
        )
        assert created.status_code == 201
        observation_id = created.json()["id"]
        review = client.post(
            f"{base}/climate-observations/{observation_id}/review",
            headers=reviewer,
            json={"decision": "verified", "note": "Cross-checked against station log."},
        )
        assert review.status_code == 200
        assert review.json()["quality_status"] == "verified"

        history = client.get(
            f"{base}/climate-observations/{observation_id}/review-history",
            headers=owner,
        )
        assert history.status_code == 200
        assert len(history.json()) == 1
        event = history.json()[0]
        assert event["action"] == "climate.observation.reviewed"
        assert event["actor_user_id"] == accepted.json()["user_id"]
        assert event["subject_user_id"] is not None
        assert event["changes"]["observation_id"] == observation_id
        assert event["changes"]["decision"] == "verified"
        assert event["changes"]["note"] == "Cross-checked against station log."

        repeated = client.post(
            f"{base}/climate-observations/{observation_id}/review",
            headers=reviewer,
            json={"decision": "rejected", "note": "Attempted second decision."},
        )
        assert repeated.status_code == 409
        history_after = client.get(
            f"{base}/climate-observations/{observation_id}/review-history",
            headers=owner,
        )
        assert history_after.status_code == 200
        assert len(history_after.json()) == 1
