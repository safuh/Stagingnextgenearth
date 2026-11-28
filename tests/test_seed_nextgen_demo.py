"""Safety and idempotency checks for founder demo catalogue seeding."""

import asyncio
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from scripts import seed_nextgen_demo
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.climate_public import (
    ClimatePublicRelease,
    ClimatePublicReleaseEvent,
)
from stagingnextgenearth.platform.models import (
    InstitutionalPartner,
    LearningAssessment,
    LearningCourse,
    LearningLesson,
    LearningModule,
    Organization,
    OrganizationPerson,
    Programme,
    PublicContentEntry,
)


def test_demo_seed_is_idempotent_and_publishes_source_catalogue_safely(
    monkeypatch, tmp_path: Path
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'founder-demo-seed.db'}"
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key=SecretStr("test-only-signing-secret-that-is-long-enough"),
    )
    monkeypatch.setattr(seed_nextgen_demo, "get_settings", lambda: settings)
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            owner = User(identifier="founder-demo@example.test", password_hash="test-hash")
            session.add(owner)
            await session.flush()
            session.add(
                Organization(
                    id="founder-demo-org",
                    name="NextGen For Earth Demo",
                    slug="nextgen-for-earth-demo",
                    country_code="KE",
                    owner_user_id=owner.id,
                )
            )
            await session.commit()

    async def inspect_seed() -> dict[str, object]:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            people = list((await session.scalars(select(OrganizationPerson))).all())
            partners = list((await session.scalars(select(InstitutionalPartner))).all())
            content = list((await session.scalars(select(PublicContentEntry))).all())
            climate_releases = list((await session.scalars(select(ClimatePublicRelease))).all())
            climate_events = list((await session.scalars(select(ClimatePublicReleaseEvent))).all())
            climate_insights = [item for item in content if item.content_type == "climate_insight"]
            gallery = next((item for item in content if item.slug == "website-gallery"), None)
            programmes = list((await session.scalars(select(Programme))).all())
            courses = list((await session.scalars(select(LearningCourse))).all())
            modules = list((await session.scalars(select(LearningModule))).all())
            lessons = list((await session.scalars(select(LearningLesson))).all())
            assessments = list((await session.scalars(select(LearningAssessment))).all())
            user_count = int(await session.scalar(select(func.count(User.id))) or 0)
            return {
                "people": len(people),
                "people_with_images": sum(bool(item.profile_image_url) for item in people),
                "partners": len(partners),
                "content": len(content),
                "climate_releases": len(climate_releases),
                "climate_releases_published": all(
                    item.state == "published" and item.provider_id == "demo-synthetic"
                    and item.data_class == "synthetic_demo"
                    and item.source_ingestion_run_id is None
                    and len(item.series_json) == 72
                    for item in climate_releases
                ),
                "climate_events": len(climate_events),
                "climate_insights": len(climate_insights),
                "climate_insight_linked": all(
                    (item.metadata_json or {}).get("release_slug") == "demo-kenya-monthly-rainfall"
                    and (item.metadata_json or {}).get("publication_slug") == "seniors-climate-seasonality-busia-kilifi"
                    for item in climate_insights
                ),
                "gallery_images": (
                    len((gallery.metadata_json or {}).get("gallery", [])) if gallery else 0
                ),
                "gallery_published": (
                    gallery is not None and gallery.publication_state == "published"
                ),
                "programmes": len(programmes),
                "courses": len(courses),
                "course_slugs": sorted(item.slug for item in courses),
                "modules": len(modules),
                "lessons": len(lessons),
                "assessments": len(assessments),
                "assessments_automated": all(
                    item.assessment_type == "quiz"
                    and len((item.configuration or {}).get("questions", [])) == 4
                    for item in assessments
                ),
                "lessons_substantive": all(
                    len(item.content or "") >= 500
                    and "Demo learning outline" not in (item.content or "")
                    for item in lessons
                ),
                "lessons_have_sources": all(
                    bool(item.resource_url) and item.resource_url.startswith("https://")
                    for item in lessons
                ),
                "courses_published": all(item.status == "published" for item in courses),
                "users": user_count,
                "people_public_verified": all(
                    item.visibility == "public" and item.review_state == "verified"
                    and item.status == "active" for item in people
                ),
                "partners_public_unverified": all(
                    item.visibility == "public"
                    and item.verification_state == "pending"
                    and item.relationship_status == "prospect"
                    for item in partners
                ),
                "content_published": all(item.publication_state == "published" for item in content),
                "programmes_planned": all(item.status == "planned" for item in programmes),
            }

    try:
        asyncio.run(prepare())
        asyncio.run(seed_nextgen_demo.seed("nextgen-for-earth-demo"))
        first = asyncio.run(inspect_seed())
        asyncio.run(seed_nextgen_demo.seed("nextgen-for-earth-demo"))
        second = asyncio.run(inspect_seed())
    finally:
        asyncio.run(engine.dispose())

    assert first == second
    assert first["people"] == len(seed_nextgen_demo.PEOPLE)
    assert first["people_with_images"] == len(seed_nextgen_demo.PEOPLE)
    assert first["partners"] == len(seed_nextgen_demo.PARTNERS)
    assert first["content"] == (
        len(seed_nextgen_demo.CONTENT)
        + len(seed_nextgen_demo.PUBLICATIONS)
        + len(seed_nextgen_demo.STORY)
        + 2
    )
    assert first["gallery_images"] >= 5
    assert first["climate_releases"] == 2
    assert first["climate_releases_published"] is True
    assert first["climate_events"] == 2
    assert first["climate_insights"] == 1
    assert first["climate_insight_linked"] is True
    assert first["gallery_published"] is True
    assert first["programmes"] == 4
    assert first["courses"] == 4
    assert first["course_slugs"] == [
        "early-career-researchers",
        "healthcare-workers",
        "indigenous-community-knowledge",
        "youth-climate-stewards",
    ]
    assert first["modules"] == 8
    assert first["lessons"] == 26
    assert first["lessons_substantive"] is True
    assert first["lessons_have_sources"] is True
    assert first["assessments"] == 4
    assert first["assessments_automated"] is True
    assert first["courses_published"] is True
    assert first["users"] == 1
    assert first["people_public_verified"] is True
    assert first["partners_public_unverified"] is True
    assert first["content_published"] is True
    assert first["programmes_planned"] is True

def test_production_seed_does_not_publish_synthetic_climate_fixtures(
    monkeypatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    url = f"sqlite+aiosqlite:///{tmp_path / 'production-seed.db'}"
    settings = SimpleNamespace(database_url=url, environment=Environment.PRODUCTION)
    monkeypatch.setattr(seed_nextgen_demo, "get_settings", lambda: settings)
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            owner = User(identifier="production-demo@example.test", password_hash="test-hash")
            session.add(owner)
            await session.flush()
            session.add(Organization(
                id="production-demo-org",
                name="Production Demo Boundary",
                slug="production-demo-boundary",
                country_code="KE",
                owner_user_id=owner.id,
            ))
            await session.commit()

    async def inspect() -> tuple[int, int]:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            releases = int(await session.scalar(
                select(func.count(ClimatePublicRelease.id))
            ) or 0)
            insights = int(await session.scalar(
                select(func.count(PublicContentEntry.id)).where(
                    PublicContentEntry.content_type == "climate_insight"
                )
            ) or 0)
            return releases, insights

    try:
        asyncio.run(prepare())
        asyncio.run(seed_nextgen_demo.seed("production-demo-boundary"))
        releases, insights = asyncio.run(inspect())
    finally:
        asyncio.run(engine.dispose())

    assert releases == 0
    assert insights == 0


