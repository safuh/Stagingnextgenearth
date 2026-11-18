"""Store encrypted ODK Central connection settings per organisation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_odk_connections"
down_revision: str | None = "0057_employment_resubmit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_odk_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("account_email", sa.String(320), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("form_mappings", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(24), nullable=True),
        sa.Column("last_sync_message", sa.String(500), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("organization_id", name="uq_odk_connection_organization"),
        sa.CheckConstraint("project_id > 0", name="ck_odk_connection_project_positive"),
    )
    op.create_index(
        "ix_odk_connections_enabled", "organization_odk_connections", ["enabled", "updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_odk_connections_enabled", table_name="organization_odk_connections")
    op.drop_table("organization_odk_connections")
