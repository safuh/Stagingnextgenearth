"""Partner registry and moderated public content."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0032_partner_cms"
down_revision: str | None = "0031_organization_people_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutional_partners",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(240), nullable=False), sa.Column("partner_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("website_url", sa.String(1000)),
        sa.Column("country_code", sa.String(2), nullable=False), sa.Column("region", sa.String(120)),
        sa.Column("relationship_status", sa.String(16), nullable=False), sa.Column("verification_state", sa.String(16), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False), sa.Column("source_url", sa.String(1000)), sa.Column("source_label", sa.String(160)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("partner_type IN ('university','government','ngo','private_sector','network','funder','community_org','other')", name="ck_institutional_partner_type"),
        sa.CheckConstraint("relationship_status IN ('prospect','active','paused','ended')", name="ck_institutional_partner_status"),
        sa.CheckConstraint("verification_state IN ('pending','verified','rejected')", name="ck_institutional_partner_verification"),
        sa.CheckConstraint("visibility IN ('private','public')", name="ck_institutional_partner_visibility"),
    )
    op.create_index("ix_institutional_partners_org_status", "institutional_partners", ["organization_id","relationship_status"])
    op.create_table(
        "programme_partners",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_id", sa.String(36), sa.ForeignKey("institutional_partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_role", sa.String(32), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("programme_id","partner_id",name="uq_programme_partner"),
        sa.CheckConstraint("partner_role IN ('implementing_partner','funding_partner','technical_partner','research_partner','community_partner')",name="ck_programme_partner_role"),
        sa.CheckConstraint("status IN ('planned','active','ended')",name="ck_programme_partner_status"),
    )
    op.create_table(
        "public_content_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_type", sa.String(24), nullable=False), sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("title", sa.String(240), nullable=False), sa.Column("summary", sa.Text()), sa.Column("body", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("publication_state", sa.String(16), nullable=False),
        sa.Column("source_url", sa.String(1000)), sa.Column("source_label", sa.String(160)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id","content_type","slug",name="uq_public_content_slug"),
        sa.CheckConstraint("content_type IN ('page','programme','training_track','initiative','research_area','impact_metric','publication')",name="ck_public_content_type"),
        sa.CheckConstraint("publication_state IN ('draft','review','approved','published','archived')",name="ck_public_content_state"),
    )
    op.create_index("ix_public_content_org_state","public_content_entries",["organization_id","publication_state"])


def downgrade() -> None:
    op.drop_index("ix_public_content_org_state", table_name="public_content_entries")
    op.drop_table("public_content_entries")
    op.drop_table("programme_partners")
    op.drop_index("ix_institutional_partners_org_status", table_name="institutional_partners")
    op.drop_table("institutional_partners")
