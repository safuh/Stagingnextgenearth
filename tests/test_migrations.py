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
