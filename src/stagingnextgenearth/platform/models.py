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


class ResearchProtocolVersion(Base):
    """Immutable-by-workflow version of a study's research protocol."""

    __tablename__ = "research_protocol_versions"
    __table_args__ = (
        UniqueConstraint("study_id", "version_number", name="uq_protocol_study_version"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'revisions_required', 'rejected')",
            name="ck_research_protocol_status",
        ),
        CheckConstraint("version_number >= 1", name="ck_protocol_version_positive"),
        Index("ix_research_protocol_versions_study_status", "study_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    sampling_and_participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_management: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_and_safeguarding: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchProtocolReviewEvent(Base):
    """Append-only review history for submitted protocol versions."""

    __tablename__ = "research_protocol_review_events"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'revisions_required', 'rejected')",
            name="ck_protocol_review_decision",
        ),
        Index("ix_protocol_review_events_protocol_time", "protocol_version_id", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    protocol_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_protocol_versions.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchEthicsReviewEvent(Base):
    """Append-only ethics committee decision history for a research study."""

    __tablename__ = "research_ethics_review_events"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'revisions_required', 'rejected', 'exempt')",
            name="ck_ethics_review_decision",
        ),
        Index("ix_ethics_review_events_study_time", "study_id", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    protocol_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_protocol_versions.id", ondelete="RESTRICT"), nullable=True
    )
    reviewer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClimateIngestionRun(Base):
    """Auditable execution record for one provider data retrieval."""

    __tablename__ = "climate_ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_climate_ingestion_run_status",
        ),
        CheckConstraint(
            "records_received >= 0 AND records_inserted >= 0 AND records_skipped >= 0",
            name="ck_climate_ingestion_run_counts",
        ),
        Index("ix_climate_ingestion_runs_org_started", "organization_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    licence: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_area: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    records_received: Mapped[int] = mapped_column(nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
        UniqueConstraint(
            "organization_id", "provider_id", "provider_record_id",
            name="uq_climate_observation_provider_record",
        ),
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
    ingestion_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("climate_ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    provider_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_record_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quality_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchDataset(Base):
    """Registry metadata and governance state for an organisation research dataset."""

    __tablename__ = "research_datasets"
    __table_args__ = (
        CheckConstraint(
            "access_classification IN ('public', 'organization', 'restricted')",
            name="ck_research_dataset_access",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected', 'archived')",
            name="ck_research_dataset_status",
        ),
        CheckConstraint(
            "collection_end IS NULL OR collection_start IS NULL "
            "OR collection_end >= collection_start",
            name="ck_research_dataset_collection_dates",
        ),
        Index("ix_research_datasets_org_status", "organization_id", "status"),
        Index("ix_research_datasets_study_id", "study_id"),
        Index("ix_research_datasets_owner_id", "owner_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    study_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0")
    format: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    access_classification: Mapped[str] = mapped_column(
        String(16), nullable=False, default="organization"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    data_dictionary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    collection_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    collection_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResearchDatasetReviewEvent(Base):
    """Append-only record of each dataset governance decision."""

    __tablename__ = "research_dataset_review_events"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_dataset_review_event_decision",
        ),
        Index("ix_dataset_review_events_dataset_time", "dataset_id", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_datasets.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchDatasetFile(Base):
    """Private object-storage reference and scan state for one dataset file version."""

    __tablename__ = "research_dataset_files"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_research_dataset_file_size"),
        CheckConstraint(
            "scan_status IN ('pending', 'clean', 'rejected')",
            name="ck_research_dataset_file_scan_status",
        ),
        CheckConstraint(
            "status IN ('upload_pending', 'quarantined', 'available', 'rejected', 'deleted')",
            name="ck_research_dataset_file_status",
        ),
        UniqueConstraint("storage_key", name="uq_research_dataset_file_storage_key"),
        UniqueConstraint(
            "dataset_id", "version", name="uq_research_dataset_file_dataset_version"
        ),
        Index("ix_research_dataset_files_dataset_status", "dataset_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_datasets.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256_hex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="upload_pending"
    )
    scan_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class ResearchDatasetFileAccessEvent(Base):
    """Append-only audit record for issuing an authorised dataset file download URL."""

    __tablename__ = "research_dataset_file_access_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('download_url_issued')",
            name="ck_dataset_file_access_event_action",
        ),
        Index(
            "ix_dataset_file_access_events_file_time",
            "dataset_file_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_dataset_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchStudyCollaborator(Base):
    """An invited or active organisation member on one research study."""

    __tablename__ = "research_study_collaborators"
    __table_args__ = (
        UniqueConstraint("study_id", "user_id", name="uq_study_collaborator_user"),
        CheckConstraint(
            "role IN ('editor', 'contributor', 'viewer')",
            name="ck_study_collaborator_role",
        ),
        CheckConstraint(
            "status IN ('invited', 'active', 'revoked')",
            name="ck_study_collaborator_status",
        ),
        Index("ix_study_collaborators_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="invited")
    invited_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
