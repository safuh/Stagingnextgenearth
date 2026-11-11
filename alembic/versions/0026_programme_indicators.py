"""Add programme indicator definitions and append-only measurements.

Revision ID: 0026_programme_indicators
Revises: 0025_programme_ops
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_programme_indicators"
down_revision: str | None = "0025_programme_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_indicators",
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
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column(
            "created_by",
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
            "direction IN ('increase', 'decrease', 'monitor')",
            name="ck_programme_indicator_direction",
        ),
        sa.UniqueConstraint("programme_id", "key", name="uq_programme_indicator_key"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_programme_indicators_programme",
        "programme_indicators",
        ["programme_id"],
    )

    op.create_table(
        "programme_indicator_measurements",
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
            "indicator_id",
            sa.String(36),
            sa.ForeignKey("programme_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence_reference", sa.String(500), nullable=True),
        sa.Column(
            "reported_by",
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
            "period_end >= period_start",
            name="ck_indicator_period_order",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_indicator_measurements_indicator_period",
        "programme_indicator_measurements",
        ["indicator_id", "period_end", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_indicator_measurements_indicator_period",
        table_name="programme_indicator_measurements",
    )
    op.drop_table("programme_indicator_measurements")
    op.drop_index(
        "ix_programme_indicators_programme",
        table_name="programme_indicators",
    )
    op.drop_table("programme_indicators")
