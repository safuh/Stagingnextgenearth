"""Add append-only programme deliverable audit history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_deliverable_events"
down_revision: str | None = "0040_learning_course_programme"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_deliverable_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "programme_id",
            sa.String(36),
            sa.ForeignKey("programmes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deliverable_id",
            sa.String(36),
            sa.ForeignKey("programme_deliverables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('created', 'assigned', 'evidence_submitted', "
            "'accepted', 'revisions_required')",
            name="ck_programme_deliverable_event_action",
        ),
    )
    op.create_index(
        "ix_programme_deliverable_events_history",
        "programme_deliverable_events",
        ["organization_id", "deliverable_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_programme_deliverable_events_history",
        table_name="programme_deliverable_events",
    )
    op.drop_table("programme_deliverable_events")
