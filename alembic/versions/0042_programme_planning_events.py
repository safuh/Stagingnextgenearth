"""Add append-only programme planning audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_planning_events"
down_revision: str | None = "0041_deliverable_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_planning_events",
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
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_title", sa.String(240), nullable=False),
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
            "entity_type IN ('goal', 'milestone', 'indicator', 'measurement')",
            name="ck_programme_planning_event_entity",
        ),
        sa.CheckConstraint(
            "action IN ('created', 'status_changed', 'measurement_recorded')",
            name="ck_programme_planning_event_action",
        ),
    )
    op.create_index(
        "ix_programme_planning_events_history",
        "programme_planning_events",
        ["organization_id", "programme_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_programme_planning_events_history",
        table_name="programme_planning_events",
    )
    op.drop_table("programme_planning_events")
