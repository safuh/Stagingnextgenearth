"""Allow audit records for multi-role membership changes.

Revision ID: 0049_membership_role_audit_action
Revises: 0048_membership_role_assignments
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_membership_role_audit_action"
down_revision: str | None = "0048_membership_role_assignments"
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
        "'membership.status_changed', 'organization.ownership_transferred')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE organization_audit_events "
        "SET action='membership.role_changed' "
        "WHERE action='membership.roles_changed'"
    )
    op.drop_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_organization_audit_event_action",
        "organization_audit_events",
        "action IN ('membership.role_changed', 'membership.status_changed', "
        "'organization.ownership_transferred')",
    )
