import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alembic_upgrade_and_downgrade() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    command = [sys.executable, "-m", "alembic"]
    subprocess.run([*command, "upgrade", "head"], check=True, env=env)

    expected_columns = {
        "users": {"id", "identifier", "password_hash", "created_at"},
        "refresh_tokens": {"token_id", "subject", "expires_at", "revoked"},
        "organizations": {"id", "name", "slug", "owner_user_id"},
        "organization_memberships": {"id", "organization_id", "user_id", "role", "status"},
        "programmes": {"id", "organization_id", "title", "slug", "status"},
        "projects": {"id", "organization_id", "programme_id", "title", "status"},
        "research_studies": {"id", "organization_id", "project_id", "title", "status"},
        "research_datasets": {
            "id",
            "organization_id",
            "study_id",
            "title",
            "version",
            "format",
            "source",
            "access_classification",
            "status",
            "data_dictionary",
            "owner_user_id",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        },
        "research_dataset_review_events": {
            "id",
            "dataset_id",
            "reviewer_user_id",
            "decision",
            "note",
            "reviewed_at",
        },
        "research_dataset_files": {
            "id",
            "dataset_id",
            "version",
            "original_filename",
            "media_type",
            "size_bytes",
            "sha256_hex",
            "storage_key",
            "status",
            "scan_status",
            "uploaded_at",
            "scanned_at",
            "created_by",
            "created_at",
        },
        "climate_observations": {
            "id",
            "organization_id",
            "study_id",
            "observed_at",
            "variable",
            "value",
            "unit",
            "latitude",
            "longitude",
            "source",
            "quality_status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        },
    }

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            for table_name, required in expected_columns.items():
                result = await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table_name"
                    ),
                    {"table_name": table_name},
                )
                actual = {row[0] for row in result}
                assert required <= actual, f"{table_name} is missing {required - actual}"
    finally:
        await engine.dispose()

    subprocess.run([*command, "downgrade", "base"], check=True, env=env)
    subprocess.run([*command, "upgrade", "head"], check=True, env=env)
