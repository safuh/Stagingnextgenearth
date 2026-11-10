"""Add research proposals, proposal review history and milestones.

Revision ID: 0014_research_planning
Revises: 0013_protocol_ethics_governance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_research_planning"
down_revision: str | None = "0013_protocol_ethics_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_study_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("study_id", sa.String(36), sa.ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("objectives", sa.Text(), nullable=False),
        sa.Column("proposed_methods", sa.Text(), nullable=False),
        sa.Column("expected_outcomes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'revisions_required', 'rejected')", name="ck_research_proposal_status"),
        sa.CheckConstraint("version_number >= 1", name="ck_research_proposal_version"),
    )
    op.create_index("ix_research_proposals_study_status", "research_study_proposals", ["study_id", "status"])
    op.create_table(
        "research_proposal_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("research_study_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('approved', 'revisions_required', 'rejected')", name="ck_proposal_review_decision"),
    )
    op.create_index("ix_proposal_review_events_proposal_time", "research_proposal_review_events", ["proposal_id", "reviewed_at"])
    op.create_table(
        "research_milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("study_id", sa.String(36), sa.ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'blocked', 'completed', 'cancelled')", name="ck_research_milestone_status"),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_research_milestone_progress"),
        sa.CheckConstraint("status != 'completed' OR progress_percent = 100", name="ck_research_milestone_completed_progress"),
    )
    op.create_index("ix_research_milestones_study_due", "research_milestones", ["study_id", "due_date"])
    op.create_index("ix_research_milestones_assignee_status", "research_milestones", ["assigned_to", "status"])


def downgrade() -> None:
    op.drop_index("ix_research_milestones_assignee_status", table_name="research_milestones")
    op.drop_index("ix_research_milestones_study_due", table_name="research_milestones")
    op.drop_table("research_milestones")
    op.drop_index("ix_proposal_review_events_proposal_time", table_name="research_proposal_review_events")
    op.drop_table("research_proposal_review_events")
    op.drop_index("ix_research_proposals_study_status", table_name="research_study_proposals")
    op.drop_table("research_study_proposals")
