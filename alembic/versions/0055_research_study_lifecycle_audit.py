"""Audit governed research-study lifecycle transitions.

Revision ID: 0055_study_lifecycle_audit
Revises: 0054_climate_review_audit
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0055_study_lifecycle_audit"
down_revision: str | None = "0054_climate_review_audit"
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
        "'research.study.status_changed')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM organization_audit_events WHERE action='research.study.status_changed'")
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
