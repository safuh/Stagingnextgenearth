"""Audit immutable research protocol and ethics decisions.

Revision ID: 0056_research_governance_audit
Revises: 0055_study_lifecycle_audit
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0056_research_governance_audit"
down_revision: str | None = "0055_study_lifecycle_audit"
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
        "'learning.mentorship.status_changed', 'climate.observation.reviewed', "
        "'research.study.status_changed', 'research.protocol.version_created', "
        "'research.protocol.submitted', 'research.protocol.reviewed', "
        "'research.ethics.review_recorded')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM organization_audit_events "
        "WHERE action IN ('research.protocol.version_created', "
        "'research.protocol.submitted', 'research.protocol.reviewed', "
        "'research.ethics.review_recorded')"
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
        "'learning.mentorship.status_changed', 'climate.observation.reviewed', "
        "'research.study.status_changed')",
    )
