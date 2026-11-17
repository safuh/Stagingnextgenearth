"""Allow audited mentorship lifecycle decisions.

Revision ID: 0052_mentorship_lifecycle_audit
Revises: 0051_employment_decision_audit
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0052_mentorship_lifecycle_audit"
down_revision: str | None = "0051_employment_decision_audit"
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
        "'learning.mentorship.status_changed')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE organization_audit_events "
        "SET action='membership.status_changed' "
        "WHERE action='learning.mentorship.status_changed'"
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
        "'volunteer_application.decided', 'employment_application.decided')",
    )
