"""Persist OData pagination cursors between bounded ODK sync runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_odk_form_cursors"
down_revision: str | None = "0059_odk_sync_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_odk_connections",
        sa.Column("form_cursors", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("organization_odk_connections", "form_cursors")
