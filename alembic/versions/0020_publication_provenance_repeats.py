"""Allow multiple field-refresh events for the same provider snapshot.

Revision ID: 0020_pub_prov_repeat
Revises: 0019_pub_meta_snap
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_pub_prov_repeat"
down_revision: str | None = "0019_pub_meta_snap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_publication_metadata_source_snapshot",
        "research_publication_metadata_sources",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_publication_metadata_source_snapshot",
        "research_publication_metadata_sources",
        [
            "publication_id",
            "provider",
            "provider_work_id",
            "metadata_sha256",
        ],
    )
