"""Merge learning and programme-deliverable migration branches.

Revision ID: 0023_merge_heads
Revises: 0022_learning_lesson_completions, 0021_programme_deliverables
"""

from collections.abc import Sequence

revision: str = "0023_merge_heads"
down_revision: tuple[str, str] = (
    "0022_learning_lesson_completions",
    "0021_programme_deliverables",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge migration heads; both parent migrations already apply their schema."""


def downgrade() -> None:
    """No schema changes are made by this merge revision."""
