"""Governed, versioned public climate releases and append-only release events."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from stagingnextgenearth.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class ClimatePublicRelease(Base):
    """A curated climate evidence package approved for anonymous publication."""

    __tablename__ = "climate_public_releases"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "slug", "version",
            name="uq_climate_public_release_org_slug_version",
        ),
        CheckConstraint(
            "state IN ('draft', 'review', 'approved', 'published', 'superseded', 'retracted')",
            name="ck_climate_public_release_state",
        ),
        CheckConstraint(
            "coverage_pct IS NULL OR (coverage_pct >= 0 AND coverage_pct <= 100)",
            name="ck_climate_public_release_coverage",
        ),
        CheckConstraint(
            "missingness_pct IS NULL OR (missingness_pct >= 0 AND missingness_pct <= 100)",
            name="ck_climate_public_release_missingness",
        ),
        CheckConstraint("version >= 1", name="ck_climate_public_release_version"),
        Index("ix_climate_public_release_public", "organization_id", "state", "slug"),
        Index("ix_climate_public_release_period", "period_start", "period_end"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    indicator: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_product: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_class: Mapped[str] = mapped_column(String(32), nullable=False)
    geography_label: Mapped[str] = mapped_column(String(200), nullable=False)
    geography_resolution: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aggregation_method: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    missingness_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(String(160), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    terms_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    citation_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_ingestion_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("climate_ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    series_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    regions_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retraction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ClimatePublicReleaseEvent(Base):
    """Append-only audit event for a public climate release lifecycle transition."""

    __tablename__ = "climate_public_release_events"
    __table_args__ = (
        Index("ix_climate_public_release_events_release", "release_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    release_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("climate_public_releases.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
