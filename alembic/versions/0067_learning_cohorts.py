"""Add tenant-scoped learning cohorts and optional enrolment assignment."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0067_learning_cohorts"
down_revision: str | None = "0066_climate_insight_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_cohorts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("programme_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'active', 'completed', 'archived')",
            name="ck_learning_cohort_status",
        ),
        sa.CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="ck_learning_cohort_capacity",
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
            name="ck_learning_cohort_dates",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["programme_id"], ["programmes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_learning_cohort_org_code"
        ),
    )
    op.create_index(
        "ix_learning_cohorts_org_status",
        "learning_cohorts",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_learning_cohorts_programme",
        "learning_cohorts",
        ["programme_id", "status"],
    )
    with op.batch_alter_table("organization_audit_events") as batch_op:
        batch_op.drop_constraint(
            "ck_organization_audit_event_action", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_organization_audit_event_action",
            "action IN ('membership.invited', 'membership.invitation_accepted', "
            "'membership.role_changed', 'membership.roles_changed', 'membership.status_changed', "
            "'organization.ownership_transferred', 'volunteer_application.decided', "
            "'employment_application.decided', 'learning.mentorship.status_changed', "
            "'climate.observation.reviewed', 'research.study.status_changed', "
            "'research.protocol.version_created', 'research.protocol.submitted', "
            "'research.protocol.reviewed', 'research.ethics.review_recorded', "
            "'learning.cohort.created', 'learning.cohort.updated', "
            "'learning.enrollment.cohort_assigned', 'learning.enrollment.cohort_unassigned')",
        )
    with op.batch_alter_table("learning_enrollments") as batch_op:
        batch_op.add_column(sa.Column("cohort_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_learning_enrollments_cohort_id_learning_cohorts",
            "learning_cohorts",
            ["cohort_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_learning_enrollments_cohort_id", ["cohort_id"], unique=False
        )


def downgrade() -> None:
    # Keep the expanded audit action constraint: immutable cohort audit rows may
    # already exist, and removing their allowed action values would invalidate history.
    with op.batch_alter_table("learning_enrollments") as batch_op:
        batch_op.drop_index("ix_learning_enrollments_cohort_id")
        batch_op.drop_constraint(
            "fk_learning_enrollments_cohort_id_learning_cohorts",
            type_="foreignkey",
        )
        batch_op.drop_column("cohort_id")
    op.drop_index("ix_learning_cohorts_programme", table_name="learning_cohorts")
    op.drop_index("ix_learning_cohorts_org_status", table_name="learning_cohorts")
    op.drop_table("learning_cohorts")
