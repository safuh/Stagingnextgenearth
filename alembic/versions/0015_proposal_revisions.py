"""Add immutable proposal revision lineage and version uniqueness.

Revision ID: 0015_proposal_revisions
Revises: 0014_research_planning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_proposal_revisions"
down_revision: str | None = "0014_research_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_study_proposals",
        sa.Column("supersedes_proposal_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_proposal_supersedes",
        "research_study_proposals",
        "research_study_proposals",
        ["supersedes_proposal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_research_proposal_study_version",
        "research_study_proposals",
        ["study_id", "version_number"],
    )
    op.create_unique_constraint(
        "uq_research_proposal_supersedes",
        "research_study_proposals",
        ["supersedes_proposal_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_research_proposal_supersedes",
        "research_study_proposals",
        type_="unique",
    )
    op.drop_constraint(
        "uq_research_proposal_study_version",
        "research_study_proposals",
        type_="unique",
    )
    op.drop_constraint(
        "fk_research_proposal_supersedes",
        "research_study_proposals",
        type_="foreignkey",
    )
    op.drop_column("research_study_proposals", "supersedes_proposal_id")
