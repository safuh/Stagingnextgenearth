"""Add versioned research protocols and ethics review history.

Revision ID: 0013_protocol_ethics_governance
Revises: 0012_researcher_profiles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_protocol_ethics_governance"
down_revision: str | None = "0012_researcher_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_protocol_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "study_id", sa.String(36),
            sa.ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("objectives", sa.Text(), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=False),
        sa.Column("sampling_and_participants", sa.Text(), nullable=True),
        sa.Column("data_management", sa.Text(), nullable=True),
        sa.Column("risk_and_safeguarding", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "created_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("study_id", "version_number", name="uq_protocol_study_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'revisions_required', 'rejected')",
            name="ck_research_protocol_status",
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_protocol_version_positive"),
    )
    op.create_index(
        "ix_research_protocol_versions_study_status",
        "research_protocol_versions", ["study_id", "status"],
    )
    op.create_table(
        "research_protocol_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "protocol_version_id", sa.String(36),
            sa.ForeignKey("research_protocol_versions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "reviewer_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'revisions_required', 'rejected')",
            name="ck_protocol_review_decision",
        ),
    )
    op.create_index(
        "ix_protocol_review_events_protocol_time",
        "research_protocol_review_events", ["protocol_version_id", "reviewed_at"],
    )
    op.create_table(
        "research_ethics_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "study_id", sa.String(36),
            sa.ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "protocol_version_id", sa.String(36),
            sa.ForeignKey("research_protocol_versions.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column(
            "reviewer_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(160), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'revisions_required', 'rejected', 'exempt')",
            name="ck_ethics_review_decision",
        ),
    )
    op.create_index(
        "ix_ethics_review_events_study_time",
        "research_ethics_review_events", ["study_id", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ethics_review_events_study_time", table_name="research_ethics_review_events")
    op.drop_table("research_ethics_review_events")
    op.drop_index(
        "ix_protocol_review_events_protocol_time",
        table_name="research_protocol_review_events",
    )
    op.drop_table("research_protocol_review_events")
    op.drop_index(
        "ix_research_protocol_versions_study_status",
        table_name="research_protocol_versions",
    )
    op.drop_table("research_protocol_versions")
