"""Add programme goals, milestones and general assignments.

Revision ID: 0028_programme_planning
Revises: 0027_programme_participation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_programme_planning"
down_revision: str | None = "0027_programme_participation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_goals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),  # noqa: E501
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),  # noqa: E501
        sa.CheckConstraint("status IN ('planned', 'active', 'achieved', 'cancelled')", name="ck_programme_goal_status"),  # noqa: E501
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programme_goals_programme_status", "programme_goals", ["programme_id", "status"])  # noqa: E501

    op.create_table(
        "programme_milestones",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("programme_goals.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),  # noqa: E501
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),  # noqa: E501
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'blocked', 'cancelled')", name="ck_programme_milestone_status"),  # noqa: E501
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programme_milestones_goal_status", "programme_milestones", ["goal_id", "status"])  # noqa: E501

    op.create_table(
        "programme_assignments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("milestone_id", sa.String(36), sa.ForeignKey("programme_milestones.id", ondelete="SET NULL"), nullable=True),  # noqa: E501
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),  # noqa: E501
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),  # noqa: E501
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),  # noqa: E501
        sa.CheckConstraint("status IN ('open', 'in_progress', 'completed', 'cancelled')", name="ck_programme_assignment_status"),  # noqa: E501
        sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name="ck_programme_assignment_priority"),  # noqa: E501
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programme_assignments_programme_status", "programme_assignments", ["programme_id", "status"])  # noqa: E501
    op.create_index("ix_programme_assignments_assignee_status", "programme_assignments", ["assigned_to", "status"])  # noqa: E501


def downgrade() -> None:
    op.drop_index("ix_programme_assignments_assignee_status", table_name="programme_assignments")
    op.drop_index("ix_programme_assignments_programme_status", table_name="programme_assignments")
    op.drop_table("programme_assignments")
    op.drop_index("ix_programme_milestones_goal_status", table_name="programme_milestones")
    op.drop_table("programme_milestones")
    op.drop_index("ix_programme_goals_programme_status", table_name="programme_goals")
    op.drop_table("programme_goals")
