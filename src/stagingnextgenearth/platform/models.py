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
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from stagingnextgenearth.core.database import Base


class GeometryPoint(UserDefinedType):
    """PostGIS WGS84 point type with a SQLite BLOB test/development fallback."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "geometry(POINT, 4326)"


@compiles(GeometryPoint, "sqlite")
def _compile_geometry_point_sqlite(
    element: GeometryPoint, compiler: object, **kw: object
) -> str:
    return "BLOB"


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
    location: Mapped[object | None] = mapped_column(GeometryPoint(), nullable=True)
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



class ResearchAnalysisRun(Base):
    """Immutable provenance record for one reproducible analysis execution."""

    __tablename__ = "research_analysis_runs"
    __table_args__ = (
        Index("ix_research_analysis_runs_dataset_created", "dataset_id", "created_at"),
        Index("ix_research_analysis_runs_study_created", "study_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_datasets.id", ondelete="RESTRICT"), nullable=False
    )
    study_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="SET NULL"), nullable=True
    )
    input_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    input_file_versions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    analysis_configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    software_name: Mapped[str] = mapped_column(String(120), nullable=False)
    software_version: Mapped[str] = mapped_column(String(80), nullable=False)
    code_revision: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    random_seed: Mapped[int | None] = mapped_column(nullable=True)
    output_artifacts: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
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


class ResearchStudyProposal(Base):
    """Versioned proposal record and its current governance state."""

    __tablename__ = "research_study_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'revisions_required', 'rejected')",
            name="ck_research_proposal_status",
        ),
        CheckConstraint("version_number >= 1", name="ck_research_proposal_version"),
        UniqueConstraint("study_id", "version_number", name="uq_research_proposal_study_version"),
        UniqueConstraint("supersedes_proposal_id", name="uq_research_proposal_supersedes"),
        Index("ix_research_proposals_study_status", "study_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    supersedes_proposal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("research_study_proposals.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_methods: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    version_number: Mapped[int] = mapped_column(nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResearchProposalReviewEvent(Base):
    """Append-only independent decisions for a research proposal."""

    __tablename__ = "research_proposal_review_events"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'revisions_required', 'rejected')",
            name="ck_proposal_review_decision",
        ),
        Index("ix_proposal_review_events_proposal_time", "proposal_id", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_study_proposals.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchMilestone(Base):
    """Assigned, date-bounded deliverable within a research study."""

    __tablename__ = "research_milestones"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="ck_research_milestone_status",
        ),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100",
                        name="ck_research_milestone_progress"),
        CheckConstraint(
            "status != 'completed' OR progress_percent = 100",
            name="ck_research_milestone_completed_progress",
        ),
        Index("ix_research_milestones_study_due", "study_id", "due_date"),
        Index("ix_research_milestones_assignee_status", "assigned_to", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResearchMilestoneEvent(Base):
    """Append-only audit event for a research milestone change."""

    __tablename__ = "research_milestone_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'updated')",
            name="ck_research_milestone_event_type",
        ),
        Index("ix_research_milestone_events_milestone_time", "milestone_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    milestone_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_milestones.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchPublication(Base):
    """Study-linked scholarly publication and external researcher identifiers."""

    __tablename__ = "research_publications"
    __table_args__ = (
        CheckConstraint(
            "publication_type IN ('article', 'book', 'chapter', 'conference_paper', "
            "'report', 'preprint', 'other')",
            name="ck_research_publication_type",
        ),
        UniqueConstraint("study_id", "doi", name="uq_research_publication_study_doi"),
        Index("ix_research_publications_study_date", "study_id", "published_on"),
        Index("ix_research_publications_openalex_id", "openalex_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_studies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    author_orcids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    publication_type: Mapped[str] = mapped_column(String(32), nullable=False)
    journal_or_venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(240), nullable=True)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openalex_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class ResearchPublicationMetadataSource(Base):
    """Append-only provenance for metadata imported from an external provider."""

    __tablename__ = "research_publication_metadata_sources"
    __table_args__ = (
        CheckConstraint(
            "provider = 'openalex'",
            name="ck_publication_metadata_source_provider",
        ),
        Index(
            "ix_publication_metadata_sources_publication_time",
            "publication_id",
            "fetched_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    publication_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_publications.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_work_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_baseline: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    imported_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    imported_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class LearningCourse(Base):
    """Organisation-owned course published to learner portals."""

    __tablename__ = "learning_courses"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_learning_course_org_slug"),
        CheckConstraint("status IN ('draft', 'published', 'archived')",
                        name="ck_learning_course_status"),
        Index("ix_learning_courses_org_status", "organization_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="blended")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearningModule(Base):
    """Ordered course module."""

    __tablename__ = "learning_modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_learning_module_position"),
        Index("ix_learning_modules_course", "course_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningLesson(Base):
    """Ordered lesson with a resource reference rather than public object credentials."""

    __tablename__ = "learning_lessons"
    __table_args__ = (
        UniqueConstraint("module_id", "position", name="uq_learning_lesson_position"),
        CheckConstraint("content_type IN ('text', 'video', 'document', 'link', 'workshop')",
                        name="ck_learning_lesson_content_type"),
        Index("ix_learning_lessons_module", "module_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    position: Mapped[int] = mapped_column(nullable=False)


class LearningLessonCompletion(Base):
    """Learner completion record for a lesson in an approved course."""

    __tablename__ = "learning_lesson_completions"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id", "lesson_id", name="uq_learning_lesson_completion"
        ),
        Index("ix_learning_lesson_completions_enrollment", "enrollment_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningEnrollment(Base):
    """Learner application and approved course registration."""

    __tablename__ = "learning_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "learner_id", name="uq_learning_enrollment_learner"),
        CheckConstraint("status IN ('applied', 'approved', 'rejected', 'completed', 'withdrawn')",
                        name="ck_learning_enrollment_status"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100",
                        name="ck_learning_enrollment_progress"),
        Index("ix_learning_enrollments_course_status", "course_id", "status"),
        Index("ix_learning_enrollments_learner_status", "learner_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="applied")
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningAssessment(Base):
    """Course assessment definition; configuration contains rubric or quiz metadata."""

    __tablename__ = "learning_assessments"
    __table_args__ = (
        CheckConstraint("assessment_type IN ('quiz', 'assignment', 'evaluation')",
                        name="ck_learning_assessment_type"),
        CheckConstraint("pass_mark >= 0 AND pass_mark <= 100",
                        name="ck_learning_assessment_pass_mark"),
        Index("ix_learning_assessments_course", "course_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    pass_mark: Mapped[int] = mapped_column(nullable=False, default=50)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class LearningAssessmentAttempt(Base):
    """Learner submission and staff evaluation."""

    __tablename__ = "learning_assessment_attempts"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)",
                        name="ck_learning_attempt_score"),
        Index("ix_learning_attempts_assessment_learner", "assessment_id", "learner_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    submission: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    score: Mapped[int | None] = mapped_column(nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    evaluated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningMentorship(Base):
    """Course-scoped mentor assignment."""

    __tablename__ = "learning_mentorships"
    __table_args__ = (
        UniqueConstraint("course_id", "mentor_id", "mentee_id", name="uq_learning_mentorship"),
        CheckConstraint("status IN ('active', 'completed', 'ended')",
                        name="ck_learning_mentorship_status"),
        Index("ix_learning_mentorship_mentor", "mentor_id", "status"),
        Index("ix_learning_mentorship_mentee", "mentee_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    mentor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    mentee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningAttendance(Base):
    """Workshop attendance record."""

    __tablename__ = "learning_attendance"
    __table_args__ = (
        UniqueConstraint("course_id", "session_key", "learner_id", name="uq_learning_attendance"),
        CheckConstraint("attendance_status IN ('present', 'late', 'excused', 'absent')",
                        name="ck_learning_attendance_status"),
        Index("ix_learning_attendance_course_date", "course_id", "session_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    session_key: Mapped[str] = mapped_column(String(100), nullable=False)
    session_title: Mapped[str] = mapped_column(String(240), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attendance_status: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningResource(Base):
    """Course or lesson resource metadata; private file access stays in storage grants."""

    __tablename__ = "learning_resources"
    __table_args__ = (
        CheckConstraint("resource_type IN ('document', 'video', 'research', 'link')",
                        name="ck_learning_resource_type"),
        Index("ix_learning_resources_course", "course_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("learning_lessons.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    storage_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class LearningCertificate(Base):
    """Revocable, publicly verifiable course completion credential."""

    __tablename__ = "learning_certificates"
    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_learning_certificate_enrollment"),
        UniqueConstraint("certificate_number", name="uq_learning_certificate_number"),
        UniqueConstraint("verification_code", name="uq_learning_certificate_verification"),
        CheckConstraint("status IN ('valid', 'revoked')", name="ck_learning_certificate_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_enrollments.id", ondelete="CASCADE"), nullable=False
    )
    certificate_number: Mapped[str] = mapped_column(String(48), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="valid")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )




class OrganizationAuditEvent(Base):
    """Append-only audit history for privileged organisation operations."""

    __tablename__ = "organization_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('membership.role_changed', 'membership.status_changed', "
            "'organization.ownership_transferred')",
            name="ck_organization_audit_event_action",
        ),
        Index(
            "ix_organization_audit_events_org_time",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    subject_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeDeliverable(Base):
    """Track an assigned programme output and its evidence review lifecycle."""

    __tablename__ = "programme_deliverables"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'submitted', 'accepted', 'revisions_required')",
            name="ck_programme_deliverable_status",
        ),
        Index("ix_programme_deliverables_programme_status", "programme_id", "status"),
        Index("ix_programme_deliverables_assignee", "assigned_to"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned")
    evidence_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class ProgrammeActivity(Base):
    """A scheduled operational activity within a programme."""

    __tablename__ = "programme_activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled')",
            name="ck_programme_activity_status",
        ),
        CheckConstraint(
            "end_at IS NULL OR end_at >= start_at",
            name="ck_programme_activity_time_order",
        ),
        Index("ix_programme_activities_programme_start", "programme_id", "start_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeVolunteerApplication(Base):
    """A volunteer's application to participate in an organisation programme."""

    __tablename__ = "programme_volunteer_applications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "programme_id", "user_id",
            name="uq_programme_volunteer_application_user",
        ),
        CheckConstraint(
            "participation_type IN ('volunteer', 'ambassador')",
            name="ck_volunteer_application_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn')",
            name="ck_volunteer_application_status",
        ),
        Index("ix_volunteer_applications_programme_status", "programme_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    participation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    interest: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeVolunteerAllocation(Base):
    """Assignment of an active volunteer member to a programme activity."""

    __tablename__ = "programme_volunteer_allocations"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_activity_volunteer"),
        CheckConstraint(
            "status IN ('assigned', 'completed', 'withdrawn')",
            name="ck_volunteer_allocation_status",
        ),
        Index("ix_volunteer_allocations_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_activities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="assigned")
    assigned_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeIndicator(Base):
    """A measurable programme outcome or output indicator."""

    __tablename__ = "programme_indicators"
    __table_args__ = (
        UniqueConstraint("programme_id", "key", name="uq_programme_indicator_key"),
        CheckConstraint(
            "direction IN ('increase', 'decrease', 'monitor')",
            name="ck_programme_indicator_direction",
        ),
        Index("ix_programme_indicators_programme", "programme_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="increase")
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeIndicatorMeasurement(Base):
    """Append-only, period-based measurement of a programme indicator."""

    __tablename__ = "programme_indicator_measurements"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_indicator_period_order"),
        Index(
            "ix_indicator_measurements_indicator_period",
            "indicator_id",
            "period_end",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    indicator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_indicators.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reported_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )




class ProgrammeGoal(Base):
    """A measurable strategic goal owned by one programme."""

    __tablename__ = "programme_goals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'active', 'achieved', 'cancelled')",
            name="ck_programme_goal_status",
        ),
        Index("ix_programme_goals_programme_status", "programme_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeMilestone(Base):
    """A dated checkpoint contributing to a programme goal."""

    __tablename__ = "programme_milestones"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'blocked', 'cancelled')",
            name="ck_programme_milestone_status",
        ),
        Index("ix_programme_milestones_goal_status", "goal_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_goals.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeAssignment(Base):
    """A general programme task assigned to an active organisation member."""

    __tablename__ = "programme_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed', 'cancelled')",
            name="ck_programme_assignment_status",
        ),
        CheckConstraint("priority IN ('low', 'normal', 'high')", name="ck_programme_assignment_priority"),  # noqa: E501
        Index("ix_programme_assignments_programme_status", "programme_id", "status"),
        Index("ix_programme_assignments_assignee_status", "assigned_to", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programme_milestones.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProgrammeParticipationRecord(Base):
    """Aggregate school/community participation record without child-level PII."""

    __tablename__ = "programme_participation_records"
    __table_args__ = (
        CheckConstraint(
            "participant_group IN ('school', 'community', 'youth_group', 'institution')",
            name="ck_programme_participant_group",
        ),
        CheckConstraint("participant_count > 0", name="ck_participant_count_positive"),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_participation_period_order",
        ),
        Index(
            "ix_programme_participation_programme_period",
            "programme_id",
            "period_end",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programme_activities.id", ondelete="SET NULL"), nullable=True
    )
    participant_group: Mapped[str] = mapped_column(String(20), nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    participant_count: Mapped[int] = mapped_column(nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
