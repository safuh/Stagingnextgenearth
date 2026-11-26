# ruff: noqa: E501

"""Add the minimum viable learning management domain.

Revision ID: 0021_learning_management
Revises: 0020_research_analysis_runs
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_learning_management"
down_revision: str | None = "0020_research_analysis_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("delivery_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_learning_course_org_slug"),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_learning_course_status"),
    )
    op.create_index("ix_learning_courses_org_status", "learning_courses", ["organization_id", "status"])
    op.create_table(
        "learning_modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "position", name="uq_learning_module_position"),
    )
    op.create_index("ix_learning_modules_course", "learning_modules", ["course_id", "position"])
    op.create_table(
        "learning_lessons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_id", sa.String(36), sa.ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("resource_url", sa.String(2000)),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("module_id", "position", name="uq_learning_lesson_position"),
        sa.CheckConstraint("content_type IN ('text', 'video', 'document', 'link', 'workshop')", name="ck_learning_lesson_content_type"),
    )
    op.create_index("ix_learning_lessons_module", "learning_lessons", ["module_id", "position"])
    op.create_table(
        "learning_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("course_id", "learner_id", name="uq_learning_enrollment_learner"),
        sa.CheckConstraint("status IN ('applied', 'approved', 'rejected', 'completed', 'withdrawn')", name="ck_learning_enrollment_status"),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_learning_enrollment_progress"),
    )
    op.create_index("ix_learning_enrollments_course_status", "learning_enrollments", ["course_id", "status"])
    op.create_index("ix_learning_enrollments_learner_status", "learning_enrollments", ["learner_id", "status"])
    op.create_table(
        "learning_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("assessment_type", sa.String(16), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("pass_mark", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("assessment_type IN ('quiz', 'assignment', 'evaluation')", name="ck_learning_assessment_type"),
        sa.CheckConstraint("pass_mark >= 0 AND pass_mark <= 100", name="ck_learning_assessment_pass_mark"),
    )
    op.create_index("ix_learning_assessments_course", "learning_assessments", ["course_id"])
    op.create_table(
        "learning_assessment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("feedback", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("evaluated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_learning_attempt_score"),
    )
    op.create_index("ix_learning_attempts_assessment_learner", "learning_assessment_attempts", ["assessment_id", "learner_id"])
    op.create_table(
        "learning_mentorships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mentee_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("assigned_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "mentor_id", "mentee_id", name="uq_learning_mentorship"),
        sa.CheckConstraint("status IN ('active', 'completed', 'ended')", name="ck_learning_mentorship_status"),
    )
    op.create_index("ix_learning_mentorship_mentor", "learning_mentorships", ["mentor_id", "status"])
    op.create_index("ix_learning_mentorship_mentee", "learning_mentorships", ["mentee_id", "status"])
    op.create_table(
        "learning_attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_key", sa.String(100), nullable=False),
        sa.Column("session_title", sa.String(240), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("learner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attendance_status", sa.String(16), nullable=False),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "session_key", "learner_id", name="uq_learning_attendance"),
        sa.CheckConstraint("attendance_status IN ('present', 'late', 'excused', 'absent')", name="ck_learning_attendance_status"),
    )
    op.create_index("ix_learning_attendance_course_date", "learning_attendance", ["course_id", "session_date"])
    op.create_table(
        "learning_resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(36), sa.ForeignKey("learning_lessons.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("resource_url", sa.String(2000)),
        sa.Column("storage_reference", sa.String(160)),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("resource_type IN ('document', 'video', 'research', 'link')", name="ck_learning_resource_type"),
    )
    op.create_index("ix_learning_resources_course", "learning_resources", ["course_id"])
    op.create_table(
        "learning_certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("learning_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("certificate_number", sa.String(48), nullable=False),
        sa.Column("verification_code", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("enrollment_id", name="uq_learning_certificate_enrollment"),
        sa.UniqueConstraint("certificate_number", name="uq_learning_certificate_number"),
        sa.UniqueConstraint("verification_code", name="uq_learning_certificate_verification"),
        sa.CheckConstraint("status IN ('valid', 'revoked')", name="ck_learning_certificate_status"),
    )


def downgrade() -> None:
    op.drop_table("learning_certificates")
    op.drop_index("ix_learning_resources_course", table_name="learning_resources")
    op.drop_table("learning_resources")
    op.drop_index("ix_learning_attendance_course_date", table_name="learning_attendance")
    op.drop_table("learning_attendance")
    op.drop_index("ix_learning_mentorship_mentee", table_name="learning_mentorships")
    op.drop_index("ix_learning_mentorship_mentor", table_name="learning_mentorships")
    op.drop_table("learning_mentorships")
    op.drop_index("ix_learning_attempts_assessment_learner", table_name="learning_assessment_attempts")
    op.drop_table("learning_assessment_attempts")
    op.drop_index("ix_learning_assessments_course", table_name="learning_assessments")
    op.drop_table("learning_assessments")
    op.drop_index("ix_learning_enrollments_learner_status", table_name="learning_enrollments")
    op.drop_index("ix_learning_enrollments_course_status", table_name="learning_enrollments")
    op.drop_table("learning_enrollments")
    op.drop_index("ix_learning_lessons_module", table_name="learning_lessons")
    op.drop_table("learning_lessons")
    op.drop_index("ix_learning_modules_course", table_name="learning_modules")
    op.drop_table("learning_modules")
    op.drop_index("ix_learning_courses_org_status", table_name="learning_courses")
    op.drop_table("learning_courses")
