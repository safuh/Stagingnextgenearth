"""Integration tests for tenant and study authorization on the evidence ledger."""

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
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'research-evidence.db'}"
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


def test_evidence_ledger_is_study_scoped_and_tenant_isolated(
    client: TestClient,
) -> None:
    lead_headers = _register(client, "evidence-lead@example.org")
    other_headers = _register(client, "evidence-other@example.org")

    organization = client.post(
        "/api/organizations",
        headers=lead_headers,
        json={"name": "Evidence Research Lab", "slug": "evidence-research-lab"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]
    study = client.post(
        f"/api/organizations/{organization_id}/research-studies",
        headers=lead_headers,
        json={"title": "Community rainfall monitoring"},
    )
    assert study.status_code == 201
    study_id = study.json()["id"]

    ledger_url = (
        f"/api/organizations/{organization_id}/research-studies/"
        f"{study_id}/evidence-ledger"
    )
    response = client.get(ledger_url, headers=lead_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["study_id"] == study_id
    assert payload["study_title"] == "Community rainfall monitoring"
    assert payload["datasets"] == []
    assert payload["analysis_runs"] == []
    assert payload["publications"] == []
    assert payload["climate"] == {
        "observation_count": 0,
        "verified_count": 0,
        "pending_count": 0,
        "rejected_count": 0,
        "first_observed_at": None,
        "last_observed_at": None,
    }
    assert payload["interpretation"] == (
        "traceability_inventory_not_independent_scientific_validation"
    )

    # The same study identifier cannot be resolved through another tenant.
    other_organization = client.post(
        "/api/organizations",
        headers=other_headers,
        json={"name": "Other Research Lab", "slug": "other-research-lab"},
    )
    assert other_organization.status_code == 201
    cross_tenant = client.get(
        f"/api/organizations/{other_organization.json()['id']}/research-studies/"
        f"{study_id}/evidence-ledger",
        headers=other_headers,
    )
    assert cross_tenant.status_code == 404

    # A user without an active organisation membership cannot read the ledger.
    outsider = client.get(ledger_url, headers=other_headers)
    assert outsider.status_code == 403


def test_evidence_ledger_rejects_invalid_result_limits(client: TestClient) -> None:
    headers = _register(client, "evidence-limit@example.org")
    organization = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Evidence Limits Lab", "slug": "evidence-limits-lab"},
    ).json()
    study = client.post(
        f"/api/organizations/{organization['id']}/research-studies",
        headers=headers,
        json={"title": "Bounded evidence study"},
    ).json()
    url = (
        f"/api/organizations/{organization['id']}/research-studies/"
        f"{study['id']}/evidence-ledger"
    )
    assert client.get(f"{url}?limit=0", headers=headers).status_code == 422
    assert client.get(f"{url}?limit=501", headers=headers).status_code == 422
