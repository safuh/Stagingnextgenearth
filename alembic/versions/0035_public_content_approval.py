"""Track CMS approval provenance before public publication."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_public_content_approval"
down_revision: str | None = "0034_employee_membership_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "public_content_entries",
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.add_column(
        "public_content_entries",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("public_content_entries", "approved_at")
    op.drop_column("public_content_entries", "approved_by")
