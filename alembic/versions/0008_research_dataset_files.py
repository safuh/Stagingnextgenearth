"""Add private research dataset file-version metadata.

Revision ID: 0008_research_dataset_files
Revises: 0007_dataset_review_history
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_research_dataset_files"
down_revision: str | None = "0007_dataset_review_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_dataset_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(36),
            sa.ForeignKey("research_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="upload_pending"),
        sa.Column("scan_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_research_dataset_file_size"),
        sa.CheckConstraint(
            "scan_status IN ('pending', 'clean', 'rejected')",
            name="ck_research_dataset_file_scan_status",
        ),
        sa.CheckConstraint(
            "status IN ('upload_pending', 'quarantined', 'available', 'rejected', 'deleted')",
            name="ck_research_dataset_file_status",
        ),
        sa.UniqueConstraint("storage_key", name="uq_research_dataset_file_storage_key"),
        sa.UniqueConstraint(
            "dataset_id", "version", name="uq_research_dataset_file_dataset_version"
        ),
    )
    op.create_index(
        "ix_research_dataset_files_dataset_status",
        "research_dataset_files",
        ["dataset_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_dataset_files_dataset_status", table_name="research_dataset_files"
    )
    op.drop_table("research_dataset_files")
