"""Add private institutional partner contact records."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_partner_contacts"
down_revision: str | None = "0037_partner_cms_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutional_partner_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "partner_id", sa.String(36),
            sa.ForeignKey("institutional_partners.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("job_title", sa.String(160), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("contact_permission", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permission_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "updated_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_partner_contact_status"),
    )
    op.create_index(
        "ix_partner_contacts_org_partner",
        "institutional_partner_contacts",
        ["organization_id", "partner_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_contacts_org_partner", table_name="institutional_partner_contacts")
    op.drop_table("institutional_partner_contacts")
