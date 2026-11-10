"""Persist climate provider ingestion runs and source record identity.

Revision ID: 0010_climate_ingestion_provenance
Revises: 0009_dataset_file_access_audit
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_climate_ingestion_provenance"
down_revision: str | None = "0009_dataset_file_access_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "climate_ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("licence", sa.String(200), nullable=True),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_area", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "started_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_climate_ingestion_run_status",
        ),
        sa.CheckConstraint(
            "records_received >= 0 AND records_inserted >= 0 AND records_skipped >= 0",
            name="ck_climate_ingestion_run_counts",
        ),
    )
    op.create_index(
        "ix_climate_ingestion_runs_org_started",
        "climate_ingestion_runs",
        ["organization_id", "started_at"],
    )
    op.add_column(
        "climate_observations",
        sa.Column(
            "ingestion_run_id",
            sa.String(36),
            sa.ForeignKey("climate_ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "climate_observations", sa.Column("provider_id", sa.String(100), nullable=True)
    )
    op.add_column(
        "climate_observations", sa.Column("provider_record_id", sa.String(200), nullable=True)
    )
    op.create_unique_constraint(
        "uq_climate_observation_provider_record",
        "climate_observations",
        ["organization_id", "provider_id", "provider_record_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_climate_observation_provider_record", "climate_observations", type_="unique"
    )
    op.drop_column("climate_observations", "provider_record_id")
    op.drop_column("climate_observations", "provider_id")
    op.drop_column("climate_observations", "ingestion_run_id")
    op.drop_index("ix_climate_ingestion_runs_org_started", table_name="climate_ingestion_runs")
    op.drop_table("climate_ingestion_runs")
