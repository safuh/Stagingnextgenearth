"""Add append-only research milestone audit events.

Revision ID: 0016_milestone_audit
Revises: 0015_proposal_revisions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_milestone_audit"
down_revision: str | None = "0015_proposal_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_milestone_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("milestone_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'updated')",
            name="ck_research_milestone_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["research_milestones.id"],
            name="fk_research_milestone_events_milestone_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_research_milestone_events_actor_user_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_milestone_events_milestone_time",
        "research_milestone_events",
        ["milestone_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_milestone_events_milestone_time",
        table_name="research_milestone_events",
    )
    op.drop_table("research_milestone_events")
