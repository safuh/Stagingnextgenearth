"""SQLAlchemy models for the optional identity module."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from stagingnextgenearth.core.database import Base


class User(Base):
    """Persisted identity record used by password authentication."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    identifier: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class ResearcherProfile(Base):
    """Optional professional profile attached one-to-one to an account."""

    __tablename__ = "researcher_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_researcher_profile_user"),
        UniqueConstraint("orcid", name="uq_researcher_profile_orcid"),
        CheckConstraint(
            "visibility IN ('private', 'organization')",
            name="ck_researcher_profile_visibility",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    biography: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    affiliation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    orcid: Mapped[str | None] = mapped_column(String(19), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    research_interests: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="private"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
