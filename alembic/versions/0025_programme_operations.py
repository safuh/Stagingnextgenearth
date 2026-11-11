"""Add programme activities and volunteer registration/allocation.

Revision ID: 0025_programme_ops
Revises: 0024_organization_audit
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_programme_ops"
down_revision: str | None = "0024_organization_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_activities",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled)", name="ck_programme_activity_status"),
        sa.CheckConstraint("end_at IS NULL OR end_at >= start_at", name="ck_programme_activity_time_order"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programme_activities_programme_start", "programme_activities", ["programme_id", "start_at"])

    op.create_table(
        "programme_volunteer_applications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participation_type", sa.String(16), nullable=False),
        sa.Column("interest", sa.Text(), nullable=False),
        sa.Column("availability", sa.String(500), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("participation_type IN ('volunteer', 'ambassador')", name="ck_volunteer_application_type"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_volunteer_application_status"),
        sa.UniqueConstraint("organization_id", "programme_id", "user_id", name="uq_programme_volunteer_application_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_volunteer_applications_programme_status", "programme_volunteer_applications", ["programme_id", "status"])

    op.create_table(
        "programme_volunteer_allocations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("programme_activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("assigned_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('assigned', 'completed', 'withdrawn')", name="ck_volunteer_allocation_status"),
        sa.UniqueConstraint("activity_id", "user_id", name="uq_activity_volunteer"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_volunteer_allocations_user_status", "programme_volunteer_allocations", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_volunteer_allocations_user_status", table_name="programme_volunteer_allocations")
    op.drop_table("programme_volunteer_allocations")
    op.drop_index("ix_volunteer_applications_programme_status", table_name="programme_volunteer_applications")
    op.drop_table("programme_volunteer_applications")
    op.drop_index("ix_programme_activities_programme_start", table_name="programme_activities")
    op.drop_table("programme_activities")
