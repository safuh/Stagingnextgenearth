"""Persist immutable research analysis execution provenance.

Revision ID: 0020_research_analysis_runs
Revises: 0019_pub_meta_snap
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_research_analysis_runs"
down_revision: str | None = "0019_pub_meta_snap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=True),
        sa.Column("input_manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("input_file_versions", sa.JSON(), nullable=False),
        sa.Column("analysis_configuration", sa.JSON(), nullable=False),
        sa.Column("software_name", sa.String(length=120), nullable=False),
        sa.Column("software_version", sa.String(length=80), nullable=False),
        sa.Column("code_revision", sa.String(length=160), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("random_seed", sa.BigInteger(), nullable=True),
        sa.Column("output_artifacts", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["research_datasets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["study_id"], ["research_studies.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_analysis_runs_dataset_created",
        "research_analysis_runs",
        ["dataset_id", "created_at"],
    )
    op.create_index(
        "ix_research_analysis_runs_study_created",
        "research_analysis_runs",
        ["study_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_analysis_runs_study_created",
        table_name="research_analysis_runs",
    )
    op.drop_index(
        "ix_research_analysis_runs_dataset_created",
        table_name="research_analysis_runs",
    )
    op.drop_table("research_analysis_runs")
