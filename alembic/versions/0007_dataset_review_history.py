"""Add append-only research dataset review history.

Revision ID: 0007_dataset_review_history
Revises: 0006_research_dataset_registry
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_dataset_review_history"
down_revision: str | None = "0006_research_dataset_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_dataset_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(36),
            sa.ForeignKey("research_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_dataset_review_event_decision",
        ),
    )
    op.create_index(
        "ix_dataset_review_events_dataset_time",
        "research_dataset_review_events",
        ["dataset_id", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dataset_review_events_dataset_time",
        table_name="research_dataset_review_events",
    )
    op.drop_table("research_dataset_review_events")
