"""Track ODK Central synchronisation executions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_odk_sync_runs"
down_revision: str | None = "0058_odk_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_odk_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("organization_odk_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("forms_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submissions_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observations_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(500), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')", name="ck_odk_sync_run_status"
        ),
    )
    op.create_index(
        "ix_odk_sync_runs_connection_started",
        "organization_odk_sync_runs",
        ["connection_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_odk_sync_runs_connection_started", table_name="organization_odk_sync_runs")
    op.drop_table("organization_odk_sync_runs")
