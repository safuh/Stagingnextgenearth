"""Add account-linked researcher profiles.

Revision ID: 0012_researcher_profiles
Revises: 0011_study_collaborators
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_researcher_profiles"
down_revision: str | None = "0011_study_collaborators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "researcher_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("biography", sa.String(2000), nullable=True),
        sa.Column("affiliation", sa.String(200), nullable=True),
        sa.Column("orcid", sa.String(19), nullable=True),
        sa.Column("website_url", sa.String(500), nullable=True),
        sa.Column("research_interests", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", name="uq_researcher_profile_user"),
        sa.UniqueConstraint("orcid", name="uq_researcher_profile_orcid"),
        sa.CheckConstraint(
            "visibility IN ('private', 'organization')",
            name="ck_researcher_profile_visibility",
        ),
    )


def downgrade() -> None:
    op.drop_table("researcher_profiles")
