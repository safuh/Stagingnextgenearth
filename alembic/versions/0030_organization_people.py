"""Add moderated organisation people directory.

Revision ID: 0030_organization_people
Revises: 0029_postgis_spatial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_organization_people"
down_revision: str | None = "0029_postgis_spatial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_people",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column("person_types", sa.JSON(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="KE"),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("profile_image_url", sa.String(length=1000), nullable=True),
        sa.Column("website_url", sa.String(length=1000), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_label", sa.String(length=160), nullable=True),
        sa.Column("review_state", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="private"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_org_people_org_visibility",
        "organization_people",
        ["organization_id", "visibility", "review_state"],
    )
    op.create_index(
        "ix_org_people_org_status",
        "organization_people",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_people_org_status", table_name="organization_people")
    op.drop_index("ix_org_people_org_visibility", table_name="organization_people")
    op.drop_table("organization_people")
