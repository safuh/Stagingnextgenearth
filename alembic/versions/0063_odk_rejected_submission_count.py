"""Persist rejected ODK submission counts in sync run history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_odk_rejected_count"
down_revision: str | None = "0062_password_changed_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_odk_sync_runs",
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("organization_odk_sync_runs", "rejected_count")
