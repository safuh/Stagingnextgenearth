"""Add persisted refresh-token rotation state.

Revision ID: 0003_refresh_tokens
Revises: 0002_identity_users
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_refresh_tokens"
down_revision: str | None = "0002_identity_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted refresh-token state."""
    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index(
        "ix_refresh_tokens_subject", "refresh_tokens", ["subject"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False
    )


def downgrade() -> None:
    """Remove persisted refresh-token state."""
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_subject", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
