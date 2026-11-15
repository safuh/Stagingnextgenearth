"""Append-only partner and CMS audit history."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_partner_cms_audit"
down_revision: str | None = "0036_volunteer_safeguard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_record_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("entity_type IN ('partner', 'content')", name="ck_org_record_audit_entity_type"),
        sa.CheckConstraint("action IN ('record.created', 'record.updated', 'record.state_changed')", name="ck_org_record_audit_action"),
    )
    op.create_index(
        "ix_org_record_audit_entity_time",
        "organization_record_audit_events",
        ["organization_id", "entity_type", "entity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_record_audit_entity_time", table_name="organization_record_audit_events")
    op.drop_table("organization_record_audit_events")
