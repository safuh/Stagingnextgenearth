"""Extend programme planning history to activities and volunteer allocations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_activity_volunteer"
down_revision: str | None = "0043_assignment_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "programme_planning_events",
        "entity_type",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.drop_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        "entity_type IN ('goal', 'milestone', 'indicator', 'measurement', "
        "'assignment', 'activity', 'volunteer_allocation')",
    )


def downgrade() -> None:
    # Events using the newly introduced entity types cannot satisfy the prior
    # check constraint. Remove only those rows before narrowing the schema.
    op.execute(
        "DELETE FROM programme_planning_events "
        "WHERE entity_type IN ('activity', 'volunteer_allocation')"
    )
    op.drop_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        "entity_type IN ('goal', 'milestone', 'indicator', 'measurement', 'assignment')",
    )
    op.alter_column(
        "programme_planning_events",
        "entity_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
