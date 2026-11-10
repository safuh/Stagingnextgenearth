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
        "research_study_proposals": {
            "id", "study_id", "title", "rationale", "objectives", "proposed_methods",
            "expected_outcomes", "status", "version_number", "created_by", "submitted_at",
            "created_at", "updated_at",
        },
        "research_proposal_review_events": {
            "id", "proposal_id", "reviewer_user_id", "decision", "note", "reviewed_at",
        },
        "research_milestones": {
            "id", "study_id", "title", "description", "assigned_to", "due_date",
            "status", "progress_percent", "created_by", "created_at", "updated_at",
        },
        "research_protocol_versions": {
            "id",
            "study_id",
            "version_number",
            "title",
            "objectives",
            "methodology",
            "sampling_and_participants",
            "data_management",
            "risk_and_safeguarding",
            "status",
            "created_by",
            "submitted_at",
            "created_at",
        },
        "research_protocol_review_events": {
            "id",
            "protocol_version_id",
            "reviewer_user_id",
            "decision",
            "note",
            "reviewed_at",
        },
        "research_ethics_review_events": {
            "id",
            "study_id",
            "protocol_version_id",
            "reviewer_user_id",
            "decision",
            "reference",
            "note",
            "reviewed_at",
        },
        "researcher_profiles": {
            "id",
            "user_id",
            "display_name",
            "biography",
            "affiliation",
            "orcid",
            "website_url",
            "research_interests",
            "visibility",
            "created_at",
            "updated_at",
        },
        "research_publications": {
            "id", "study_id", "title", "authors", "author_orcids",
            "publication_type", "journal_or_venue", "publisher", "published_on",
            "doi", "openalex_id", "url", "abstract", "created_by", "created_at",
        },
        "research_publication_metadata_sources": {
            "id", "publication_id", "provider", "provider_work_id", "source_url",
            "metadata_sha256", "metadata_snapshot", "imported_fields", "imported_by", "fetched_at",
        },
        "research_study_collaborators": {
            "id",
            "study_id",
            "organization_id",
            "user_id",
            "role",
            "status",
            "invited_by",
            "created_at",
            "accepted_at",
            "revoked_at",
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
        "research_dataset_file_access_events": {
            "id",
            "dataset_file_id",
            "user_id",
            "action",
            "created_at",
        },
        "climate_ingestion_runs": {
            "id", "organization_id", "provider_id", "source_name", "licence",
            "requested_start", "requested_end", "requested_area", "status",
            "records_received", "records_inserted", "records_skipped", "started_by",
            "started_at", "finished_at",
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
            "ingestion_run_id",
            "provider_id",
            "provider_record_id",
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
