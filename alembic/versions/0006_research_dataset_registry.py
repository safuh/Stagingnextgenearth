"""Create the governed research dataset registry.

Revision ID: 0006_research_dataset_registry
Revises: 0005_climate_observation_review
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_research_dataset_registry"
down_revision: str | None = "0005_climate_observation_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            sa.String(36),
            sa.ForeignKey("research_studies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(40), nullable=False, server_default="1.0"),
        sa.Column("format", sa.String(40), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("license", sa.String(120), nullable=True),
        sa.Column("access_classification", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("data_dictionary", sa.JSON(), nullable=False),
        sa.Column("collection_start", sa.Date(), nullable=True),
        sa.Column("collection_end", sa.Date(), nullable=True),
        sa.Column(
            "owner_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "access_classification IN ('public', 'organization', 'restricted')",
            name="ck_research_dataset_access",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected', 'archived')",
            name="ck_research_dataset_status",
        ),
        sa.CheckConstraint(
            "collection_end IS NULL OR collection_start IS NULL "
            "OR collection_end >= collection_start",
            name="ck_research_dataset_collection_dates",
        ),
    )
    op.create_index(
        "ix_research_datasets_org_status",
        "research_datasets",
        ["organization_id", "status"],
    )
    op.create_index("ix_research_datasets_study_id", "research_datasets", ["study_id"])
    op.create_index("ix_research_datasets_owner_id", "research_datasets", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_research_datasets_owner_id", table_name="research_datasets")
    op.drop_index("ix_research_datasets_study_id", table_name="research_datasets")
    op.drop_index("ix_research_datasets_org_status", table_name="research_datasets")
    op.drop_table("research_datasets")
