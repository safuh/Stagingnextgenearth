"""Audit organisation membership invitations and acceptance."""

from collections.abc import Sequence

from alembic import op

revision: str = "0064_membership_invite_audit"
down_revision: str | None = "0063_odk_rejected_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = (
    "'membership.invited', 'membership.invitation_accepted', "
    "'membership.role_changed', 'membership.roles_changed', 'membership.status_changed', "
    "'organization.ownership_transferred', 'volunteer_application.decided', "
    "'employment_application.decided', 'learning.mentorship.status_changed', "
    "'climate.observation.reviewed', 'research.study.status_changed', "
    "'research.protocol.version_created', 'research.protocol.submitted', "
    "'research.protocol.reviewed', 'research.ethics.review_recorded'"
)


def upgrade() -> None:
    with op.batch_alter_table("organization_audit_events") as batch_op:
        batch_op.drop_constraint("ck_organization_audit_event_action", type_="check")
        batch_op.create_check_constraint(
            "ck_organization_audit_event_action", f"action IN ({_ACTIONS})"
        )


def downgrade() -> None:
    with op.batch_alter_table("organization_audit_events") as batch_op:
        batch_op.drop_constraint("ck_organization_audit_event_action", type_="check")
        batch_op.create_check_constraint(
            "ck_organization_audit_event_action",
            "action IN ('membership.role_changed', 'membership.roles_changed', "
            "'membership.status_changed', 'organization.ownership_transferred', "
            "'volunteer_application.decided', 'employment_application.decided', "
            "'learning.mentorship.status_changed', 'climate.observation.reviewed', "
            "'research.study.status_changed', 'research.protocol.version_created', "
            "'research.protocol.submitted', 'research.protocol.reviewed', "
            "'research.ethics.review_recorded')",
        )
