"""Add safeguarding confirmation to climate observations.

The ORM model includes this field, so existing installations need an explicit
schema migration before SQLAlchemy can select climate observation records.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_climate_safeguarding"
down_revision: str | None = "0045_activity_attendance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "climate_observations",
        sa.Column(
            "safeguarding_confirmed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("climate_observations", "safeguarding_confirmed")
