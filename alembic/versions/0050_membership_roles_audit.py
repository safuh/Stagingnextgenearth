"""Permit append-only audit events for secondary membership role changes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050_membership_roles_audit"
down_revision: str | None = "0049_employment_resubmission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = (
    "'membership.role_changed', 'membership.roles_changed', "
    "'membership.status_changed', 'organization.ownership_transferred'"
)


def upgrade() -> None:
    with op.batch_alter_table("organization_audit_events") as batch:
        batch.drop_constraint("ck_organization_audit_event_action", type_="check")
        batch.create_check_constraint(
            "ck_organization_audit_event_action", f"action IN ({_ACTIONS})"
        )


def downgrade() -> None:
    existing = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM organization_audit_events "
            "WHERE action = 'membership.roles_changed' LIMIT 1"
        )
    ).first()
    if existing is not None:
        raise RuntimeError(
            "Cannot remove membership.roles_changed while immutable audit events exist"
        )
    with op.batch_alter_table("organization_audit_events") as batch:
        batch.drop_constraint("ck_organization_audit_event_action", type_="check")
        batch.create_check_constraint(
            "ck_organization_audit_event_action",
            "action IN ('membership.role_changed', 'membership.status_changed', "
            "'organization.ownership_transferred')",
        )
