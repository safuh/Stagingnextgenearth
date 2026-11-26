"""Store publication metadata baselines for safe refreshes.

Revision ID: 0019_pub_meta_snap
Revises: 0018_pub_meta_prov
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_pub_meta_snap"
down_revision: str | None = "0018_pub_meta_prov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_publication_metadata_sources",
        sa.Column("metadata_baseline", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_publication_metadata_sources", "metadata_baseline")
