"""Allow append-only climate observation review audit events.

Revision ID: 0054_climate_review_audit
Revises: 0053_assessment_eval_history
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0054_climate_review_audit"
down_revision: str | None = "0053_assessment_eval_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        "action IN ('membership.role_changed', 'membership.roles_changed', "
        "'membership.status_changed', 'organization.ownership_transferred', "
        "'volunteer_application.decided', 'employment_application.decided', "
        "'learning.mentorship.status_changed', 'climate.observation.reviewed')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM organization_audit_events "
        "WHERE action='climate.observation.reviewed'"
    )
    op.drop_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        "action IN ('membership.role_changed', 'membership.roles_changed', "
        "'membership.status_changed', 'organization.ownership_transferred', "
        "'volunteer_application.decided', 'employment_application.decided', "
        "'learning.mentorship.status_changed')",
    )
