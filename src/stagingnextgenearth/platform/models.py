"""Core organisational, programme, research, and climate data models."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from stagingnextgenearth.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class Organization(Base):
    """Tenant boundary for an organisation using the platform."""

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        Index("ix_organizations_owner_user_id", "owner_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Membership(Base):
    """A user's role and access state inside one organisation."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        CheckConstraint(
            "role IN ('admin', 'programme_manager', 'researcher', "
            "'youth_volunteer', 'institutional_partner')",
            name="ck_membership_role",
        ),
        CheckConstraint(
            "status IN ('invited', 'active', 'suspended')",
            name="ck_membership_status",
        ),
        Index("ix_memberships_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Programme(Base):
    """An organisation-level programme grouping related projects."""

    __tablename__ = "programmes"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_programme_org_slug"),
        CheckConstraint(
            "status IN ('draft', 'planned', 'active', 'completed', 'archived')",
            name="ck_programme_status",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_programme_date_order",
        ),
        Index("ix_programmes_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Project(Base):
    """A deliverable project belonging to an organisation and optionally a programme."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'active', 'on_hold', 'completed', 'archived')",
            name="ck_project_status",
        ),
        Index("ix_projects_org_status", "organization_id", "status"),
        Index("ix_projects_programme_id", "programme_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    county: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchStudy(Base):
    """A research study with controlled organisational and project ownership."""

    __tablename__ = "research_studies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('concept', 'protocol', 'active', 'completed', 'published', 'archived')",
            name="ck_research_study_status",
        ),
        Index("ix_research_studies_org_status", "organization_id", "status"),
        Index("ix_research_studies_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    study_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="concept")
    lead_researcher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ethics_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ClimateObservation(Base):
    """A sourced, timestamped climate observation linked to a project or study."""

    __tablename__ = "climate_observations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_observation_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_observation_longitude"),
        CheckConstraint(
            "quality_status IN ('pending', 'verified', 'rejected')",
            name="ck_observation_quality_status",
        ),
        Index("ix_climate_observations_org_time", "organization_id", "observed_at"),
        Index("ix_climate_observations_variable_time", "variable", "observed_at"),
        Index("ix_climate_observations_study_id", "study_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    study_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    variable: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    quality_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
