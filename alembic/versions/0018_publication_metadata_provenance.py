"""Record provenance for externally imported publication metadata.

Revision ID: 0018_publication_metadata_provenance
Revises: 0017_research_publications
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_publication_metadata_provenance"
down_revision: str | None = "0017_research_publications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_publication_metadata_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("publication_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_work_id", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("metadata_sha256", sa.String(length=64), nullable=False),
        sa.Column("imported_fields", sa.JSON(), nullable=False),
        sa.Column("imported_by", sa.String(length=36), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider = 'openalex'",
            name="ck_publication_metadata_source_provider",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["research_publications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "provider",
            "provider_work_id",
            "metadata_sha256",
            name="uq_publication_metadata_source_snapshot",
        ),
    )
    op.create_index(
        "ix_publication_metadata_sources_publication_time",
        "research_publication_metadata_sources",
        ["publication_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_publication_metadata_sources_publication_time",
        table_name="research_publication_metadata_sources",
    )
    op.drop_table("research_publication_metadata_sources")
