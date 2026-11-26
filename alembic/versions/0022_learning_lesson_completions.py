"""Track lesson completion as a prerequisite for course certification.

Revision ID: 0022_learning_lesson_completions
Revises: 0021_learning_management
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_learning_lesson_completions"
down_revision: str | None = "0021_learning_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_lesson_completions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.String(36),
            sa.ForeignKey("learning_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("learning_lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "enrollment_id", "lesson_id", name="uq_learning_lesson_completion"
        ),
    )
    op.create_index(
        "ix_learning_lesson_completions_enrollment",
        "learning_lesson_completions",
        ["enrollment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_lesson_completions_enrollment",
        table_name="learning_lesson_completions",
    )
    op.drop_table("learning_lesson_completions")
