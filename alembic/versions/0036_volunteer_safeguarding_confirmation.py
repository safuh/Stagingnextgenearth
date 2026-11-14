"""Record safeguarding confirmation for volunteer application decisions."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_volunteer_safeguarding_confirmation"
down_revision: str | None = "0035_public_content_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "programme_volunteer_applications",
        sa.Column("safeguarding_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("programme_volunteer_applications", "safeguarding_confirmed")
