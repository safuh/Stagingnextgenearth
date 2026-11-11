"""Add append-only audit events for privileged organisation operations.

Revision ID: 0024_organization_audit
Revises: 0023_merge_heads
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_organization_audit"
down_revision: str | None = "0023_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_audit_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subject_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('membership.role_changed', 'membership.status_changed', "
            "'organization.ownership_transferred')",
            name="ck_organization_audit_event_action",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_audit_events_org_time",
        "organization_audit_events",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_audit_events_org_time",
        table_name="organization_audit_events",
    )
    op.drop_table("organization_audit_events")
