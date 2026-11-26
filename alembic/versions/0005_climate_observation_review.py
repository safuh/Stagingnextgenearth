"""Add review audit fields to climate observations.

Revision ID: 0005_climate_observation_review
Revises: 0004_platform_domain
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_climate_observation_review"
down_revision: str | None = "0004_platform_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "climate_observations",
        sa.Column(
            "reviewed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "climate_observations",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "climate_observations",
        sa.Column("review_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("climate_observations", "review_note")
    op.drop_column("climate_observations", "reviewed_at")
    op.drop_column("climate_observations", "reviewed_by")
