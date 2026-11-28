"""Add course cohorts and append-only enrolment events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_learning_cohorts"
down_revision: str | None = "0064_membership_invite_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_cohorts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("programme_id", sa.String(length=36), nullable=True),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrollment_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrollment_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("safeguarding_policy_version", sa.String(length=100), nullable=True),
        sa.Column("consent_policy_version", sa.String(length=100), nullable=True),
        sa.Column("retention_policy_version", sa.String(length=100), nullable=True),
        sa.Column("minor_access_policy_version", sa.String(length=100), nullable=True),
        sa.Column("readiness_reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("readiness_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'active', 'completed', 'cancelled', 'archived')",
            name="ck_learning_cohort_status",
        ),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_learning_cohort_capacity"),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="ck_learning_cohort_date_order",
        ),
        sa.CheckConstraint(
            "enrollment_closes_at IS NULL OR enrollment_opens_at IS NULL "
            "OR enrollment_closes_at >= enrollment_opens_at",
            name="ck_learning_cohort_enrollment_window",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["programme_id"], ["programmes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["learning_courses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["readiness_reviewed_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "slug", name="uq_learning_cohort_course_slug"),
        sa.UniqueConstraint("organization_id", "code", name="uq_learning_cohort_org_code"),
    )
    op.create_index(
        "ix_learning_cohorts_org_status", "learning_cohorts", ["organization_id", "status"]
    )
    op.create_index(
        "ix_learning_cohorts_course_status", "learning_cohorts", ["course_id", "status"]
    )

    with op.batch_alter_table("learning_enrollments") as batch_op:
        batch_op.add_column(sa.Column("cohort_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_learning_enrollment_cohort",
            "learning_cohorts",
            ["cohort_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_learning_enrollments_cohort", "learning_enrollments", ["cohort_id"])

    op.create_table(
        "learning_enrollment_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("enrollment_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=True),
        sa.Column("from_cohort_id", sa.String(length=36), nullable=True),
        sa.Column("to_cohort_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('applied', 'approved', 'rejected', 'transferred')",
            name="ck_learning_enrollment_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["learning_enrollments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_cohort_id"], ["learning_cohorts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["to_cohort_id"], ["learning_cohorts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_enrollment_events_enrollment_created",
        "learning_enrollment_events",
        ["enrollment_id", "created_at"],
    )
    op.create_index(
        "ix_learning_enrollment_events_org_created",
        "learning_enrollment_events",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_enrollment_events_org_created", table_name="learning_enrollment_events"
    )
    op.drop_index(
        "ix_learning_enrollment_events_enrollment_created",
        table_name="learning_enrollment_events",
    )
    op.drop_table("learning_enrollment_events")
    op.drop_index("ix_learning_enrollments_cohort", table_name="learning_enrollments")
    with op.batch_alter_table("learning_enrollments") as batch_op:
        batch_op.drop_constraint("fk_learning_enrollment_cohort", type_="foreignkey")
        batch_op.drop_column("cohort_id")
    op.drop_index("ix_learning_cohorts_course_status", table_name="learning_cohorts")
    op.drop_index("ix_learning_cohorts_org_status", table_name="learning_cohorts")
    op.drop_table("learning_cohorts")
