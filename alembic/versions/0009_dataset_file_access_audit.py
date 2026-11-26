"""Add research dataset file download access audit events.

Revision ID: 0009_dataset_file_access_audit
Revises: 0008_research_dataset_files
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_dataset_file_access_audit"
down_revision: str | None = "0008_research_dataset_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_dataset_file_access_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "dataset_file_id",
            sa.String(36),
            sa.ForeignKey("research_dataset_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('download_url_issued')",
            name="ck_dataset_file_access_event_action",
        ),
    )
    op.create_index(
        "ix_dataset_file_access_events_file_time",
        "research_dataset_file_access_events",
        ["dataset_file_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dataset_file_access_events_file_time",
        table_name="research_dataset_file_access_events",
    )
    op.drop_table("research_dataset_file_access_events")
