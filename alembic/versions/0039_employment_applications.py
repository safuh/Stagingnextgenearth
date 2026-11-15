"""Add secure organisation employment applications."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_employment_applications"
down_revision: str | None = "0038_partner_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_employment_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("desired_position", sa.String(160), nullable=False),
        sa.Column("qualifications", sa.Text(), nullable=False),
        sa.Column("experience_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','approved','rejected','withdrawn')", name="ck_employment_application_status"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_employment_application_org_user"),
    )
    op.create_index(
        "ix_employment_applications_org_status",
        "organization_employment_applications",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_employment_applications_org_status", table_name="organization_employment_applications")
    op.drop_table("organization_employment_applications")
