"""Funding register access, integrity, reporting and tenant-isolation tests."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


def test_funding_register_workflow_and_boundaries(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'funding.db'}"
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
        client.post(
            "/api/auth/register",
            json={
                "identifier": "funding-owner@example.org",
                "password": "correct horse battery staple",
            },
        )
        login = client.post(
            "/api/auth/login",
            json={
                "identifier": "funding-owner@example.org",
                "password": "correct horse battery staple",
            },
        )
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        organization = client.post(
            "/api/organizations",
            headers=headers,
            json={
                "name": "Funding Test Organisation",
                "slug": "funding-test-org",
            },
        ).json()
        organization_id = organization["id"]
        base = f"/api/organizations/{organization_id}/funding"

        opportunity = client.post(
            f"{base}/opportunities",
            headers=headers,
            json={
                "title": '=HYPERLINK("https://example.invalid")',
                "donor_name": "Climate Research Fund",
                "deadline": "2027-02-01",
                "expected_amount": "12000.00",
                "currency": "KES",
                "status": "submitted",
            },
        )
        assert opportunity.status_code == 201, opportunity.text
        opportunity_id = opportunity.json()["id"]
        updated_opportunity = client.patch(
            f"{base}/opportunities/{opportunity_id}",
            headers=headers,
            json={"status": "awarded"},
        )
        assert updated_opportunity.status_code == 200
        assert updated_opportunity.json()["status"] == "awarded"
        assert (
            client.patch(
                f"{base}/opportunities/{opportunity_id}",
                headers=headers,
                json={"title": None},
            ).status_code
            == 422
        )

        award = client.post(
            f"{base}/awards",
            headers=headers,
            json={
                "title": "Community Climate Evidence Grant",
                "donor_name": '=HYPERLINK("https://example.invalid")',
                "opportunity_id": opportunity_id,
                "award_amount": "10000.00",
                "currency": "KES",
                "restrictions": "Research equipment and field activities only.",
                "start_date": "2026-12-01",
                "end_date": "2027-11-30",
                "reporting_deadline": "2027-06-30",
                "status": "active",
            },
        )
        assert award.status_code == 201, award.text
        award_id = award.json()["id"]
        updated_award = client.patch(
            f"{base}/awards/{award_id}",
            headers=headers,
            json={"reporting_deadline": "2027-07-15"},
        )
        assert updated_award.status_code == 200
        assert updated_award.json()["reporting_deadline"] == "2027-07-15"

        programme = client.post(
            f"/api/organizations/{organization_id}/programmes",
            headers=headers,
            json={"title": "Climate Research", "slug": "climate-research"},
        )
        assert programme.status_code == 201, programme.text
        budget = client.post(
            f"{base}/awards/{award_id}/budget-lines",
            headers=headers,
            json={
                "name": "Field data collection",
                "budget_amount": "8000.00",
                "programme_id": programme.json()["id"],
            },
        )
        assert budget.status_code == 201, budget.text
        budget_id = budget.json()["id"]
        overallocated = client.post(
            f"{base}/awards/{award_id}/budget-lines",
            headers=headers,
            json={
                "name": "Equipment",
                "budget_amount": "3000.00",
            },
        )
        assert overallocated.status_code == 409
        reduced_award = client.patch(
            f"{base}/awards/{award_id}",
            headers=headers,
            json={"award_amount": "7000.00"},
        )
        assert reduced_award.status_code == 409

        for entry_type, amount in (("pledge", "5000.00"), ("commitment", "4000.00")):
            response = client.post(
                f"{base}/awards/{award_id}/ledger",
                headers=headers,
                json={
                    "entry_type": entry_type,
                    "amount": amount,
                    "occurred_on": "2026-12-10",
                    "description": f"Recorded {entry_type}",
                },
            )
            assert response.status_code == 201, response.text

        expenditure = client.post(
            f"{base}/awards/{award_id}/ledger",
            headers=headers,
            json={
                "entry_type": "expenditure",
                "amount": "3000.00",
                "occurred_on": "2026-12-15",
                "description": "Field team transport and logistics",
                "budget_line_id": budget_id,
            },
        )
        assert expenditure.status_code == 201, expenditure.text
        over_spend = client.post(
            f"{base}/awards/{award_id}/ledger",
            headers=headers,
            json={
                "entry_type": "expenditure",
                "amount": "6000.00",
                "occurred_on": "2026-12-16",
                "description": "Exceeds remaining budget line",
                "budget_line_id": budget_id,
            },
        )
        assert over_spend.status_code == 409

        report = client.get(f"{base}/report", headers=headers)
        assert report.status_code == 200, report.text
        summary = report.json()[0]
        assert summary["award_amount"] == "10000.00"
        assert summary["budgeted_amount"] == "8000.00"
        assert summary["pledged_amount"] == "5000.00"
        assert summary["committed_amount"] == "4000.00"
        assert summary["expenditure_amount"] == "3000.00"
        assert summary["unallocated_amount"] == "2000.00"

        exported = client.get(f"{base}/report.csv", headers=headers)
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("text/csv")
        assert "'=HYPERLINK" in exported.text
        assert "payment" not in exported.text.lower()

        audit = client.get(f"{base}/audit-events", headers=headers)
        assert audit.status_code == 200
        assert {event["entity_type"] for event in audit.json()} == {
            "opportunity",
            "award",
            "budget_line",
            "ledger_entry",
        }
        assert any(
            event["entity_type"] == "opportunity" and event["action"] == "record.updated"
            for event in audit.json()
        )
        assert any(
            event["entity_type"] == "award" and event["action"] == "record.updated"
            for event in audit.json()
        )

        # A normal employee may not read sensitive funding records.
        client.post(
            "/api/auth/register",
            json={
                "identifier": "funding-employee@example.org",
                "password": "correct horse battery staple",
            },
        )
        invitation = client.post(
            f"/api/organizations/{organization_id}/memberships",
            headers=headers,
            json={"identifier": "funding-employee@example.org", "role": "employee"},
        )
        employee_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "funding-employee@example.org",
                "password": "correct horse battery staple",
            },
        )
        employee_headers = {"Authorization": "Bearer " + employee_login.json()["access_token"]}
        accepted = client.post(
            f"/api/organizations/{organization_id}/memberships/{invitation.json()['id']}/accept",
            headers=employee_headers,
        )
        assert accepted.status_code == 200
        assert client.get(f"{base}/report", headers=employee_headers).status_code == 403
        assert (
            client.post(
                f"{base}/opportunities",
                headers=employee_headers,
                json={
                    "title": "Restricted",
                    "donor_name": "Private Donor",
                },
            ).status_code
            == 403
        )

        # Another tenant cannot attach this tenant's opportunity or award.
        client.post(
            "/api/auth/register",
            json={
                "identifier": "other-owner@example.org",
                "password": "correct horse battery staple",
            },
        )
        other_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "other-owner@example.org",
                "password": "correct horse battery staple",
            },
        )
        other_headers = {"Authorization": "Bearer " + other_login.json()["access_token"]}
        other_org = client.post(
            "/api/organizations",
            headers=other_headers,
            json={
                "name": "Other Organisation",
                "slug": "other-funding-org",
            },
        ).json()
        other_base = f"/api/organizations/{other_org['id']}/funding"
        cross_tenant = client.post(
            f"{other_base}/awards",
            headers=other_headers,
            json={
                "title": "Cross tenant",
                "donor_name": "Donor",
                "award_amount": "1.00",
                "opportunity_id": opportunity_id,
            },
        )
        assert cross_tenant.status_code == 404
        assert (
            client.get(
                f"/api/organizations/{other_org['id']}/funding/awards/{award_id}/ledger",
                headers=other_headers,
            ).status_code
            == 404
        )
