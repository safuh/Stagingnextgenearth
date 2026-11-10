"""Establish the initial, domain-neutral migration boundary.

Revision ID: 0001_foundation
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the foundation revision; product schemas belong to consuming apps."""
    pass


def downgrade() -> None:
    """Revert the foundation revision."""
    pass
