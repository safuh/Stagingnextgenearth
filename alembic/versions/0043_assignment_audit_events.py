"""Allow assignment lifecycle events in programme planning history."""

from collections.abc import Sequence

from alembic import op

revision: str = "0043_assignment_events"
down_revision: str | None = "0042_planning_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.drop_constraint(
        "ck_programme_planning_event_action",
        "programme_planning_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_programme_planning_event_action",
        "programme_planning_events",
        "action IN ('created', 'assigned', 'status_changed', 'measurement_recorded')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_programme_planning_event_action",
        "programme_planning_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_programme_planning_event_action",
        "programme_planning_events",
        "action IN ('created', 'status_changed', 'measurement_recorded')",
    )
    op.drop_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_programme_planning_event_entity",
        "programme_planning_events",
        "entity_type IN ('goal', 'milestone', 'indicator', 'measurement')",
    )
