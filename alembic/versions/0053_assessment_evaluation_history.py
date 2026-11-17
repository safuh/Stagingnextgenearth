"""Persist append-only assessment evaluation history.

Revision ID: 0053_assessment_evaluation_history
Revises: 0052_mentorship_lifecycle_audit
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0053_assessment_evaluation_history"
down_revision: str | None = "0052_mentorship_lifecycle_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_assessment_evaluations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(length=36),
            sa.ForeignKey("learning_assessment_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("previous_score", sa.Integer(), nullable=True),
        sa.Column("previous_feedback", sa.Text(), nullable=True),
        sa.Column(
            "evaluated_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_learning_assessment_evaluation_score",
        ),
    )
    op.create_index(
        "ix_learning_assessment_evaluations_attempt",
        "learning_assessment_evaluations",
        ["attempt_id", "evaluated_at"],
    )
    connection = op.get_bind()
    existing_evaluations = connection.execute(
        sa.text(
            "SELECT id, score, feedback, evaluated_by, evaluated_at "
            "FROM learning_assessment_attempts "
            "WHERE evaluated_at IS NOT NULL AND evaluated_by IS NOT NULL"
        )
    ).mappings()
    for row in existing_evaluations:
        connection.execute(
            sa.text(
                "INSERT INTO learning_assessment_evaluations "
                "(id, attempt_id, score, feedback, previous_score, "
                "previous_feedback, evaluated_by, evaluated_at) "
                "VALUES (:id, :attempt_id, :score, :feedback, NULL, NULL, "
                ":evaluated_by, :evaluated_at)"
            ),
            {
                "id": str(uuid4()),
                "attempt_id": row["id"],
                "score": row["score"],
                "feedback": row["feedback"],
                "evaluated_by": row["evaluated_by"],
                "evaluated_at": row["evaluated_at"],
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_assessment_evaluations_attempt",
        table_name="learning_assessment_evaluations",
    )
    op.drop_table("learning_assessment_evaluations")
