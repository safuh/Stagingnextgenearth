"""Associate learning courses with organisation programmes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_learning_course_programme"
down_revision: str | None = "0039_employment_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_courses",
        sa.Column(
            "programme_id",
            sa.String(36),
            sa.ForeignKey("programmes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_learning_courses_programme_id",
        "learning_courses",
        ["programme_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_courses_programme_id", table_name="learning_courses")
    op.drop_column("learning_courses", "programme_id")
