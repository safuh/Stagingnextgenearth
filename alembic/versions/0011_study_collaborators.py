"""Add study-level collaborator invitations and access roles.

Revision ID: 0011_study_collaborators
Revises: 0010_climate_ingest
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_study_collaborators"
down_revision: str | None = "0010_climate_ingest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_study_collaborators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "study_id",
            sa.String(36),
            sa.ForeignKey("research_studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="invited"),
        sa.Column(
            "invited_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("study_id", "user_id", name="uq_study_collaborator_user"),
        sa.CheckConstraint(
            "role IN ('editor', 'contributor', 'viewer')",
            name="ck_study_collaborator_role",
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'revoked')",
            name="ck_study_collaborator_status",
        ),
    )
    op.create_index(
        "ix_study_collaborators_user_status",
        "research_study_collaborators",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_study_collaborators_user_status",
        table_name="research_study_collaborators",
    )
    op.drop_table("research_study_collaborators")
