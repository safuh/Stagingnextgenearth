"""Add study publication metadata registry.

Revision ID: 0017_research_publications
Revises: 0016_milestone_audit
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_research_publications"
down_revision: str | None = "0016_milestone_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_publications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("author_orcids", sa.JSON(), nullable=False),
        sa.Column("publication_type", sa.String(length=32), nullable=False),
        sa.Column("journal_or_venue", sa.String(length=300), nullable=True),
        sa.Column("publisher", sa.String(length=240), nullable=True),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("openalex_id", sa.String(length=32), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "publication_type IN ('article', 'book', 'chapter', 'conference_paper', 'report', 'preprint', 'other')",
            name="ck_research_publication_type",
        ),
        sa.ForeignKeyConstraint(["study_id"], ["research_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "doi", name="uq_research_publication_study_doi"),
    )
    op.create_index(
        "ix_research_publications_study_date",
        "research_publications", ["study_id", "published_on"],
    )
    op.create_index(
        "ix_research_publications_openalex_id", "research_publications", ["openalex_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_research_publications_openalex_id", table_name="research_publications")
    op.drop_index("ix_research_publications_study_date", table_name="research_publications")
    op.drop_table("research_publications")
