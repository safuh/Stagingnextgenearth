"""Integration tests for reproducible research export manifests."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.platform.models import ResearchDatasetFile


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


def test_dataset_export_manifest_requires_approval_and_is_reproducible(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'research-exports.db'}"
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

    with TestClient(create_app(settings)) as client:
        owner_headers = _register(client, "export-owner@example.org")
        reviewer_headers = _register(client, "export-reviewer@example.org")
        organization = client.post(
            "/api/organizations",
            headers=owner_headers,
            json={"name": "Export Research Lab", "slug": "export-research-lab"},
        )
        assert organization.status_code == 201
        organization_id = organization.json()["id"]

        invitation = client.post(
            f"/api/organizations/{organization_id}/memberships",
            headers=owner_headers,
            json={
                "identifier": "export-reviewer@example.org",
                "role": "programme_manager",
            },
        )
        assert invitation.status_code == 201
        accepted = client.post(
            f"/api/organizations/{organization_id}/memberships/"
            f"{invitation.json()['id']}/accept",
            headers=reviewer_headers,
        )
        assert accepted.status_code == 200

        datasets_url = f"/api/organizations/{organization_id}/research-datasets"
        created = client.post(
            datasets_url,
            headers=owner_headers,
            json={
                "title": "Community rainfall observations",
                "description": "Daily observations collected under the study protocol.",
                "version": "1.2",
                "format": "csv",
                "source": "Community weather stations",
                "license": "CC-BY-4.0",
                "access_classification": "organization",
                "data_dictionary": {
                    "observed_on": {"type": "date", "unit": None},
                    "rainfall_mm": {"type": "number", "unit": "mm"},
                },
                "collection_start": "2025-01-01",
                "collection_end": "2025-12-31",
            },
        )
        assert created.status_code == 201
        dataset_id = created.json()["id"]
        manifest_url = f"{datasets_url}/{dataset_id}/export-manifest"

        premature = client.get(manifest_url, headers=owner_headers)
        assert premature.status_code == 409

        submitted = client.post(
            f"{datasets_url}/{dataset_id}/submit",
            headers=owner_headers,
        )
        assert submitted.status_code == 200
        reviewed = client.post(
            f"{datasets_url}/{dataset_id}/review",
            headers=reviewer_headers,
            json={"decision": "approved", "note": "Metadata and provenance reviewed."},
        )
        assert reviewed.status_code == 200

        file_engine = create_async_engine(database_url)
        file_time = datetime.now(UTC)

        async def add_file_versions() -> None:
            session_factory = async_sessionmaker(file_engine, expire_on_commit=False)
            async with session_factory() as session:
                session.add_all(
                    [
                        ResearchDatasetFile(
                            id="clean-file-version",
                            dataset_id=dataset_id,
                            version=1,
                            original_filename="rainfall.csv",
                            media_type="text/csv",
                            size_bytes=128,
                            sha256_hex="a" * 64,
                            storage_key="private/clean-file",
                            status="available",
                            scan_status="clean",
                            uploaded_at=file_time,
                            scanned_at=file_time,
                            created_by=created.json()["owner_user_id"],
                        ),
                        ResearchDatasetFile(
                            id="quarantined-file-version",
                            dataset_id=dataset_id,
                            version=2,
                            original_filename="pending.csv",
                            media_type="text/csv",
                            size_bytes=64,
                            storage_key="private/quarantined-file",
                            status="quarantined",
                            scan_status="pending",
                            uploaded_at=file_time,
                            created_by=created.json()["owner_user_id"],
                        ),
                    ]
                )
                await session.commit()

        asyncio.run(add_file_versions())
        await file_engine.dispose()

        first = client.get(manifest_url, headers=owner_headers)
        assert first.status_code == 200
        manifest = first.json()
        assert manifest["schema_version"] == "1.0"
        assert len(manifest["manifest_sha256"]) == 64
        assert manifest["dataset"]["id"] == dataset_id
        assert manifest["dataset"]["title"] == "Community rainfall observations"
        assert manifest["dataset"]["data_dictionary"]["rainfall_mm"]["unit"] == "mm"
        assert [item["file_id"] for item in manifest["dataset"]["files"]] == [
            "clean-file-version"
        ]
        assert manifest["dataset"]["files"][0]["sha256"] == "a" * 64
        assert manifest["dataset"]["excluded_file_versions"] == 1
        assert "storage_key" not in manifest["dataset"]["files"][0]

        second = client.get(manifest_url, headers=owner_headers)
        assert second.status_code == 200
        assert second.json()["manifest_sha256"] == manifest["manifest_sha256"]
