"""Record volunteer application decisions in the organisation audit trail.

Revision ID: 0050_volunteer_decision_audit
Revises: 0049_membership_audit_action
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0050_volunteer_decision_audit"
down_revision: str | None = "0049_membership_audit_action"
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
        "'volunteer_application.decided')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE organization_audit_events "
        "SET action='membership.status_changed' "
        "WHERE action='volunteer_application.decided'"
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
        "'membership.status_changed', 'organization.ownership_transferred')",
    )
