"""Add the initial NextGen for Earth organisational and research domain.

Revision ID: 0004_platform_domain
Revises: 0003_refresh_tokens
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_platform_domain"
down_revision: str | None = "0003_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index(
        "ix_organizations_owner_user_id",
        "organizations",
        ["owner_user_id"],
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_membership_org_user",
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'programme_manager', 'researcher', "
            "'youth_volunteer', 'institutional_partner')",
            name="ck_membership_role",
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'suspended')",
            name="ck_membership_status",
        ),
    )
    op.create_index(
        "ix_memberships_user_status",
        "organization_memberships",
        ["user_id", "status"],
    )

    op.create_table(
        "programmes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_programme_org_slug",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'planned', 'active', 'completed', 'archived')",
            name="ck_programme_status",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_programme_date_order",
        ),
    )
    op.create_index(
        "ix_programmes_org_status",
        "programmes",
        ["organization_id", "status"],
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "programme_id",
            sa.String(36),
            sa.ForeignKey("programmes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("county", sa.String(120), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'on_hold', 'completed', 'archived')",
            name="ck_project_status",
        ),
    )
    op.create_index(
        "ix_projects_org_status",
        "projects",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_projects_programme_id",
        "projects",
        ["programme_id"],
    )

    op.create_table(
        "research_studies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("study_type", sa.String(80), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "lead_researcher_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("ethics_reference", sa.String(160), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('concept', 'protocol', 'active', 'completed', "
            "'published', 'archived')",
            name="ck_research_study_status",
        ),
    )
    op.create_index(
        "ix_research_studies_org_status",
        "research_studies",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_research_studies_project_id",
        "research_studies",
        ["project_id"],
    )

    op.create_table(
        "climate_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            sa.String(36),
            sa.ForeignKey("research_studies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("variable", sa.String(80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("quality_status", sa.String(16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_observation_latitude",
        ),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_observation_longitude",
        ),
        sa.CheckConstraint(
            "quality_status IN ('pending', 'verified', 'rejected')",
            name="ck_observation_quality_status",
        ),
    )
    op.create_index(
        "ix_climate_observations_org_time",
        "climate_observations",
        ["organization_id", "observed_at"],
    )
    op.create_index(
        "ix_climate_observations_variable_time",
        "climate_observations",
        ["variable", "observed_at"],
    )
    op.create_index(
        "ix_climate_observations_study_id",
        "climate_observations",
        ["study_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_climate_observations_study_id",
        table_name="climate_observations",
    )
    op.drop_index(
        "ix_climate_observations_variable_time",
        table_name="climate_observations",
    )
    op.drop_index(
        "ix_climate_observations_org_time",
        table_name="climate_observations",
    )
    op.drop_table("climate_observations")
    op.drop_index(
        "ix_research_studies_project_id",
        table_name="research_studies",
    )
    op.drop_index(
        "ix_research_studies_org_status",
        table_name="research_studies",
    )
    op.drop_table("research_studies")
    op.drop_index("ix_projects_programme_id", table_name="projects")
    op.drop_index("ix_projects_org_status", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_programmes_org_status", table_name="programmes")
    op.drop_table("programmes")
    op.drop_index(
        "ix_memberships_user_status",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")
    op.drop_index(
        "ix_organizations_owner_user_id",
        table_name="organizations",
    )
    op.drop_table("organizations")
