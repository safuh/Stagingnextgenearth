"""Add tenant-scoped learning cohorts, course links and learner membership."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_learning_cohorts"
down_revision: str | None = "0064_membership_invite_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = (
    "'membership.invited', 'membership.invitation_accepted', "
    "'membership.role_changed', 'membership.roles_changed', 'membership.status_changed', "
    "'organization.ownership_transferred', 'volunteer_application.decided', "
    "'employment_application.decided', 'learning.mentorship.status_changed', "
    "'learning.cohort.created', 'learning.cohort.course_linked', "
    "'learning.cohort.member_added', 'learning.cohort.member_status_changed', "
    "'learning.cohort.status_changed', "
    "'climate.observation.reviewed', 'research.study.status_changed', "
    "'research.protocol.version_created', 'research.protocol.submitted', "
    "'research.protocol.reviewed', 'research.ethics.review_recorded'"
)


def upgrade() -> None:
    op.create_table(
        "learning_cohorts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("programme_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'active', 'closed', 'archived')",
            name="ck_learning_cohort_status",
        ),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_learning_cohort_capacity"),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_learning_cohort_date_order",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_learning_cohort_org_slug"),
    )
    op.create_index(
        "ix_learning_cohorts_org_status", "learning_cohorts", ["organization_id", "status"]
    )
    op.create_index("ix_learning_cohorts_programme", "learning_cohorts", ["programme_id"])

    op.create_table(
        "learning_cohort_courses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("cohort_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohort_id"], ["learning_cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["learning_courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "course_id", name="uq_learning_cohort_course"),
    )
    op.create_index(
        "ix_learning_cohort_courses_org",
        "learning_cohort_courses",
        ["organization_id", "cohort_id"],
    )

    op.create_table(
        "learning_cohort_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("cohort_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'withdrawn', 'suspended')",
            name="ck_learning_cohort_membership_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohort_id"], ["learning_cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "learner_id", name="uq_learning_cohort_learner"),
    )
    op.create_index(
        "ix_learning_cohort_memberships_org_status",
        "learning_cohort_memberships",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_learning_cohort_memberships_cohort", "learning_cohort_memberships", ["cohort_id"]
    )
    op.create_index(
        "ix_learning_cohort_memberships_learner", "learning_cohort_memberships", ["learner_id"]
    )

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
            "action IN ('membership.invited', 'membership.invitation_accepted', "
            "'membership.role_changed', 'membership.roles_changed', 'membership.status_changed', "
            "'organization.ownership_transferred', 'volunteer_application.decided', "
            "'employment_application.decided', 'learning.mentorship.status_changed', "
            "'climate.observation.reviewed', 'research.study.status_changed', "
            "'research.protocol.version_created', 'research.protocol.submitted', "
            "'research.protocol.reviewed', 'research.ethics.review_recorded')",
        )
    op.drop_index(
        "ix_learning_cohort_memberships_learner", table_name="learning_cohort_memberships"
    )
    op.drop_index(
        "ix_learning_cohort_memberships_cohort", table_name="learning_cohort_memberships"
    )
    op.drop_index(
        "ix_learning_cohort_memberships_org_status", table_name="learning_cohort_memberships"
    )
    op.drop_table("learning_cohort_memberships")
    op.drop_index(
        "ix_learning_cohort_courses_org", table_name="learning_cohort_courses"
    )
    op.drop_table("learning_cohort_courses")
    op.drop_index(
        "ix_learning_cohorts_programme", table_name="learning_cohorts"
    )
    op.drop_index(
        "ix_learning_cohorts_org_status", table_name="learning_cohorts"
    )
    op.drop_table("learning_cohorts")
