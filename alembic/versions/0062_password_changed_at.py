"""Track password changes to invalidate already-issued access JWTs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_password_changed_at"
down_revision: str | None = "0061_funding_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
