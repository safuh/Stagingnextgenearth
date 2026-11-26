# ruff: noqa: E501
"""Add governed public climate release records and lifecycle events."""

import sqlalchemy as sa
from alembic import op

revision = "0065_climate_public_releases"
down_revision = "0064_membership_invite_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "climate_public_releases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("indicator", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=False),
        sa.Column("provider_product", sa.String(length=160), nullable=False),
        sa.Column("provider_version", sa.String(length=100)),
        sa.Column("data_class", sa.String(length=32), nullable=False),
        sa.Column("geography_label", sa.String(length=200), nullable=False),
        sa.Column("geography_resolution", sa.String(length=120), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline", sa.String(length=200)),
        sa.Column("aggregation_method", sa.Text(), nullable=False),
        sa.Column("coverage_pct", sa.Float()),
        sa.Column("missingness_pct", sa.Float()),
        sa.Column("uncertainty_summary", sa.Text()),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.Column("license_name", sa.String(length=160), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("terms_url", sa.String(length=1000)),
        sa.Column("citation_url", sa.String(length=1000)),
        sa.Column("source_ingestion_run_id", sa.String(length=36), sa.ForeignKey("climate_ingestion_runs.id", ondelete="SET NULL")),
        sa.Column("series_json", sa.JSON(), nullable=False),
        sa.Column("regions_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retracted_at", sa.DateTime(timezone=True)),
        sa.Column("retraction_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "slug", "version", name="uq_climate_public_release_org_slug_version"),
        sa.CheckConstraint("state IN ('draft', 'review', 'approved', 'published', 'superseded', 'retracted')", name="ck_climate_public_release_state"),
        sa.CheckConstraint("coverage_pct IS NULL OR (coverage_pct >= 0 AND coverage_pct <= 100)", name="ck_climate_public_release_coverage"),
        sa.CheckConstraint("missingness_pct IS NULL OR (missingness_pct >= 0 AND missingness_pct <= 100)", name="ck_climate_public_release_missingness"),
        sa.CheckConstraint("version >= 1", name="ck_climate_public_release_version"),
    )
    op.create_index("ix_climate_public_release_public", "climate_public_releases", ["organization_id", "state", "slug"])
    op.create_index("ix_climate_public_release_period", "climate_public_releases", ["period_start", "period_end"])
    op.create_table(
        "climate_public_release_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_id", sa.String(length=36), sa.ForeignKey("climate_public_releases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_state", sa.String(length=16)),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_climate_public_release_events_release", "climate_public_release_events", ["release_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_climate_public_release_events_release", table_name="climate_public_release_events")
    op.drop_table("climate_public_release_events")
    op.drop_index("ix_climate_public_release_period", table_name="climate_public_releases")
    op.drop_index("ix_climate_public_release_public", table_name="climate_public_releases")
    op.drop_table("climate_public_releases")
