"""Add explainable learning risk policy and staff intervention records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0068_learning_interventions"
down_revision: str | None = "0067_learning_cohorts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("learning_cohorts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "inactivity_threshold_days",
                sa.Integer(),
                nullable=False,
                server_default="14",
            )
        )
        batch_op.add_column(
            sa.Column("absence_threshold", sa.Integer(), nullable=False, server_default="2")
        )
        batch_op.add_column(
            sa.Column("absence_window_days", sa.Integer(), nullable=False, server_default="30")
        )
        batch_op.add_column(
            sa.Column("overdue_grace_days", sa.Integer(), nullable=False, server_default="2")
        )
        batch_op.create_check_constraint(
            "ck_learning_cohort_inactivity_threshold",
            "inactivity_threshold_days BETWEEN 1 AND 90",
        )
        batch_op.create_check_constraint(
            "ck_learning_cohort_absence_threshold",
            "absence_threshold BETWEEN 1 AND 20",
        )
        batch_op.create_check_constraint(
            "ck_learning_cohort_absence_window",
            "absence_window_days BETWEEN 7 AND 90",
        )
        batch_op.create_check_constraint(
            "ck_learning_cohort_overdue_grace_days",
            "overdue_grace_days BETWEEN 0 AND 30",
        )

    op.create_table(
        "learning_interventions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("cohort_id", sa.String(length=36), nullable=False),
        sa.Column("enrollment_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_to", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('open', 'in_progress', 'resolved', 'cancelled')",
            name="ck_learning_intervention_status",
        ),
        sa.CheckConstraint("length(note) > 0", name="ck_learning_intervention_note"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohort_id"], ["learning_cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["learning_enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_interventions_org_status_due",
        "learning_interventions",
        ["organization_id", "status", "due_date"],
    )
    op.create_index(
        "ix_learning_interventions_cohort_status",
        "learning_interventions",
        ["cohort_id", "status"],
    )
    op.create_index(
        "ix_learning_interventions_enrollment",
        "learning_interventions",
        ["enrollment_id"],
    )

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
            "'research.protocol.reviewed', 'research.ethics.review_recorded', "
            "'learning.cohort.created', 'learning.cohort.updated', "
            "'learning.enrollment.cohort_assigned', 'learning.enrollment.cohort_unassigned', "
            "'learning.intervention.created', 'learning.intervention.updated', "
            "'learning.intervention.resolved')",
        )


def downgrade() -> None:
    # Keep the expanded audit vocabulary so immutable intervention history remains valid.
    op.drop_index("ix_learning_interventions_enrollment", table_name="learning_interventions")
    op.drop_index("ix_learning_interventions_cohort_status", table_name="learning_interventions")
    op.drop_index("ix_learning_interventions_org_status_due", table_name="learning_interventions")
    op.drop_table("learning_interventions")
    with op.batch_alter_table("learning_cohorts") as batch_op:
        batch_op.drop_constraint("ck_learning_cohort_overdue_grace_days", type_="check")
        batch_op.drop_constraint("ck_learning_cohort_absence_window", type_="check")
        batch_op.drop_constraint("ck_learning_cohort_absence_threshold", type_="check")
        batch_op.drop_constraint("ck_learning_cohort_inactivity_threshold", type_="check")
        batch_op.drop_column("overdue_grace_days")
        batch_op.drop_column("absence_window_days")
        batch_op.drop_column("absence_threshold")
        batch_op.drop_column("inactivity_threshold_days")
