"""Add aggregate programme participation records.

Revision ID: 0027_programme_participation
Revises: 0026_programme_indicators
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_programme_participation"
down_revision: str | None = "0026_programme_indicators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_participation_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "programme_id",
            sa.String(36),
            sa.ForeignKey("programmes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            sa.String(36),
            sa.ForeignKey("programme_activities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("participant_group", sa.String(20), nullable=False),
        sa.Column("group_name", sa.String(200), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence_reference", sa.String(500), nullable=True),
        sa.Column(
            "recorded_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "participant_group IN ('school', 'community', 'youth_group', 'institution')",
            name="ck_programme_participant_group",
        ),
        sa.CheckConstraint(
            "participant_count > 0",
            name="ck_participant_count_positive",
        ),
        sa.CheckConstraint(
            "period_end >= period_start",
            name="ck_participation_period_order",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_programme_participation_programme_period",
        "programme_participation_records",
        ["programme_id", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_programme_participation_programme_period",
        table_name="programme_participation_records",
    )
    op.drop_table("programme_participation_records")
