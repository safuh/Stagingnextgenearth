"""Safety and idempotency checks for founder demo catalogue seeding."""

import asyncio
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from scripts import seed_nextgen_demo
from stagingnextgenearth.core.config import DeploymentStage, Environment, Settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.climate_public import (
    ClimatePublicRelease,
    ClimatePublicReleaseEvent,
)
from stagingnextgenearth.platform.models import (
    InstitutionalPartner,
    LearningAssessment,
    LearningCohort,
    LearningCourse,
    LearningEnrollment,
    LearningLesson,
    LearningLessonCompletion,
    LearningModule,
    Membership,
    MembershipRole,
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
        climate_demo_seed_enabled=True,
        learning_demo_seed_enabled=True,
        deployment_stage=DeploymentStage.STAGING,
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
            publications = [item for item in content if item.content_type == "publication"]
            climate_releases = list((await session.scalars(select(ClimatePublicRelease))).all())
            climate_events = list((await session.scalars(select(ClimatePublicReleaseEvent))).all())
            climate_insights = [item for item in content if item.content_type == "climate_insight"]
            gallery = next((item for item in content if item.slug == "website-gallery"), None)
            programmes = list((await session.scalars(select(Programme))).all())
            cohorts = list((await session.scalars(select(LearningCohort))).all())
            courses = list((await session.scalars(select(LearningCourse))).all())
            modules = list((await session.scalars(select(LearningModule))).all())
            lessons = list((await session.scalars(select(LearningLesson))).all())
            assessments = list((await session.scalars(select(LearningAssessment))).all())
            user_count = int(await session.scalar(select(func.count(User.id))) or 0)
            enrollments = list((await session.scalars(select(LearningEnrollment))).all())
            demo_user_ids = set((await session.scalars(
                select(User.id).where(User.identifier.like("%@demo.nextgenforearth.test"))
            )).all())
            demo_enrollments = [
                item for item in enrollments if item.learner_id in demo_user_ids
            ]
            completions = list((await session.scalars(select(LearningLessonCompletion))).all())
            owner = await session.scalar(
                select(User).where(User.identifier == "founder-demo@example.test")
            )
            owner_membership = None
            if owner is not None:
                owner_membership = await session.scalar(
                    select(Membership).where(
                        Membership.organization_id == "founder-demo-org",
                        Membership.user_id == owner.id,
                    )
                )
            owner_learner_role = False
            if owner_membership is not None:
                owner_learner_role = await session.scalar(
                    select(MembershipRole.id).where(
                        MembershipRole.membership_id == owner_membership.id,
                        MembershipRole.role == "learner",
                    )
                ) is not None
            return {
                "people": len(people),
                "people_with_images": sum(bool(item.profile_image_url) for item in people),
                "partners": len(partners),
                "content": len(content),
                "publication_metadata_complete": (
                    len(publications) == len(seed_nextgen_demo.PUBLICATIONS)
                    and all(
                        isinstance((item.metadata_json or {}).get("authors"), str)
                        and isinstance((item.metadata_json or {}).get("publisher"), str)
                        and isinstance((item.metadata_json or {}).get("year"), int)
                        and (item.metadata_json or {}).get("year_provenance")
                        == (
                            "Seed catalogue year; verify against the DOI landing page "
                            "before treating as canonical."
                        )
                        and isinstance((item.metadata_json or {}).get("editorial_topic"), str)
                        and (item.metadata_json or {}).get("editorial_topic_provenance")
                        == (
                            "Editorial discovery tag assigned by the demo seed; "
                            "not a source-reported keyword."
                        )
                        and (item.metadata_json or {}).get("doi")
                        == (item.source_url or "").removeprefix("https://doi.org/")
                        for item in publications
                    )
                ),
                "publication_topics": sorted({
                    (item.metadata_json or {}).get("editorial_topic")
                    for item in publications
                    if isinstance((item.metadata_json or {}).get("editorial_topic"), str)
                }),
                "climate_releases": len(climate_releases),
                "climate_releases_published": all(
                    item.state == "published" and item.provider_id == "demo-synthetic"
                    and item.data_class == "synthetic_demo"
                    and item.source_ingestion_run_id is None
                    and len(item.series_json) == 72
                    for item in climate_releases
                ),
                "climate_events": len(climate_events),
                "climate_release_publication_times": sorted(
                    item.published_at.isoformat() for item in climate_releases
                ),
                "climate_insights": len(climate_insights),
                "climate_insight_publication_time": (
                    climate_insights[0].published_at.isoformat() if climate_insights else None
                ),
                "climate_insight_linked": all(
                    (item.metadata_json or {}).get("release_slug") == "demo-kenya-monthly-rainfall"
                    and (item.metadata_json or {}).get("publication_slug")
                    == "seniors-climate-seasonality-busia-kilifi"
                    for item in climate_insights
                ),
                "gallery_images": (
                    len((gallery.metadata_json or {}).get("gallery", [])) if gallery else 0
                ),
                "gallery_published": (
                    gallery is not None and gallery.publication_state == "published"
                ),
                "programmes": len(programmes),
                "cohorts": len(cohorts),
                "cohort_codes": sorted(item.code for item in cohorts),
                "cohorts_draft": all(item.status == "draft" for item in cohorts),
                "courses": len(courses),
                "course_slugs": sorted(item.slug for item in courses),
                "published_courses": sum(item.status == "published" for item in courses),
                "draft_courses": sum(item.status == "draft" for item in courses),
                "modules": len(modules),
                "lessons": len(lessons),
                "assessments": len(assessments),
                "staff_course_title": next(
                    item.title for item in courses if item.slug == "early-career-researchers"
                ),
                "staff_module_title": next(
                    item.title for item in modules
                    if item.course_id == next(
                        course.id for course in courses
                        if course.slug == "early-career-researchers"
                    ) and item.position == 1
                ),
                "staff_lesson_content": next(
                    item.content for item in lessons
                    if item.module_id == next(
                        module.id for module in modules
                        if module.course_id == next(
                            course.id for course in courses
                            if course.slug == "early-career-researchers"
                        ) and module.position == 1
                    ) and item.position == 1
                ),
                "staff_draft_course_title": next(
                    item.title for item in courses
                    if item.slug == "early-career-researchers-authoring-draft"
                ),
                "staff_draft_module_title": next(
                    item.title for item in modules
                    if item.course_id == next(
                        course.id for course in courses
                        if course.slug == "early-career-researchers-authoring-draft"
                    ) and item.position == 1
                ),
                "staff_draft_lesson_content": next(
                    item.content for item in lessons
                    if item.module_id == next(
                        module.id for module in modules
                        if module.course_id == next(
                            course.id for course in courses
                            if course.slug == "early-career-researchers-authoring-draft"
                        ) and module.position == 1
                    ) and item.position == 1
                ),
                "draft_course_title": next(
                    item.title for item in courses
                    if item.slug == "early-career-researchers-authoring-draft"
                ),
                "draft_module_title": next(
                    item.title for item in modules
                    if item.course_id == next(
                        course.id for course in courses
                        if course.slug == "early-career-researchers-authoring-draft"
                    ) and item.position == 1
                ),
                "draft_lesson_content": next(
                    item.content for item in lessons
                    if item.module_id == next(
                        module.id for module in modules
                        if module.course_id == next(
                            course.id for course in courses
                            if course.slug == "early-career-researchers-authoring-draft"
                        ) and module.position == 1
                    ) and item.position == 1
                ),
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
                "courses_published": all(
                    item.status == "published"
                    for item in courses if not item.slug.endswith("-authoring-draft")
                ),
                "draft_courses_editable": all(
                    item.status == "draft"
                    for item in courses if item.slug.endswith("-authoring-draft")
                ),
                "users": user_count,
                "demo_enrollments": len(demo_enrollments),
                "demo_enrollments_completed": all(
                    item.status == "completed" and item.progress_percent == 100
                    for item in demo_enrollments
                ),
                "demo_lesson_completions": len(completions),
                "owner_learner_role": owner_learner_role,
                "owner_enrollment_in_progress": any(
                    item.learner_id == (owner.id if owner else None)
                    and item.status == "approved" and item.progress_percent == 20
                    for item in enrollments
                ),
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

        async def apply_staff_edits() -> None:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                course = await session.scalar(select(LearningCourse).where(
                    LearningCourse.slug == "early-career-researchers"
                ))
                assert course is not None
                course.title = "Staff-authored research pathway"
                module = await session.scalar(select(LearningModule).where(
                    LearningModule.course_id == course.id,
                    LearningModule.position == 1,
                ))
                assert module is not None
                module.title = "Staff-authored module"
                lesson = await session.scalar(select(LearningLesson).where(
                    LearningLesson.module_id == module.id,
                    LearningLesson.position == 1,
                ))
                assert lesson is not None
                lesson.content = (
                    "Staff-authored lesson content; preserve this revision. "
                    + ("Updated field note. " * 35)
                )

                draft_course = await session.scalar(select(LearningCourse).where(
                    LearningCourse.slug == "early-career-researchers-authoring-draft"
                ))
                assert draft_course is not None
                draft_course.title = "Staff-authored draft pathway"
                draft_module = await session.scalar(select(LearningModule).where(
                    LearningModule.course_id == draft_course.id,
                    LearningModule.position == 1,
                ))
                assert draft_module is not None
                draft_module.title = "Staff-authored draft module"
                draft_lesson = await session.scalar(select(LearningLesson).where(
                    LearningLesson.module_id == draft_module.id,
                    LearningLesson.position == 1,
                ))
                assert draft_lesson is not None
                draft_lesson.content = (
                    "Staff-authored draft lesson; preserve this revision. "
                    + ("Draft field note. " * 35)
                )
                await session.commit()

        asyncio.run(apply_staff_edits())
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
    assert first["publication_metadata_complete"] is True
    assert first["publication_topics"] == sorted({
        "Climate & Health", "Youth & Climate", "Kenya Field Study",
        "Climate Science", "Maternal Health", "Youth Health",
        "Community Engagement",
    })
    assert first["gallery_images"] >= 5
    assert first["climate_releases"] == 2
    assert first["climate_releases_published"] is True
    assert first["climate_events"] == 2
    assert first["climate_insights"] == 1
    assert first["climate_insight_linked"] is True
    assert first["gallery_published"] is True
    assert first["programmes"] == 4
    assert first["cohorts"] == 4
    assert first["cohorts_draft"] is True
    assert first["cohort_codes"] == [
        "DEMO-EARLY-CAREER-RESEARCHERS",
        "DEMO-HEALTHCARE-WORKERS",
        "DEMO-INDIGENOUS-COMMUNITY-KNOWLEDGE",
        "DEMO-YOUTH-CLIMATE-STEWARDS",
    ]
    assert first["courses"] == 8
    assert first["course_slugs"] == [
        "early-career-researchers",
        "early-career-researchers-authoring-draft",
        "healthcare-workers",
        "healthcare-workers-authoring-draft",
        "indigenous-community-knowledge",
        "indigenous-community-knowledge-authoring-draft",
        "youth-climate-stewards",
        "youth-climate-stewards-authoring-draft",
    ]
    assert first["published_courses"] == 4
    assert first["draft_courses"] == 4
    assert first["draft_courses_editable"] is True
    assert first["modules"] == 56
    assert first["lessons"] == 172
    assert first["lessons_substantive"] is True
    assert first["lessons_have_sources"] is True
    assert first["assessments"] == 8
    assert first["assessments_automated"] is True
    assert first["courses_published"] is True
    assert first["staff_course_title"] == "Staff-authored research pathway"
    assert first["staff_module_title"] == "Staff-authored module"
    assert str(first["staff_lesson_content"]).startswith(
        "Staff-authored lesson content; preserve this revision."
    )
    assert first["draft_course_title"] == "Staff-authored draft pathway"
    assert first["draft_module_title"] == "Staff-authored draft module"
    assert str(first["draft_lesson_content"]).startswith(
        "Staff-authored draft lesson; preserve this revision."
    )
    assert first["users"] == 5
    assert first["demo_enrollments"] == 4
    assert first["demo_enrollments_completed"] is True
    assert first["demo_lesson_completions"] == 91
    assert first["owner_learner_role"] is True
    assert first["owner_enrollment_in_progress"] is True
    assert first["people_public_verified"] is True
    assert first["partners_public_unverified"] is True
    assert first["content_published"] is True
    assert first["programmes_planned"] is True

def test_production_seed_does_not_publish_synthetic_climate_fixtures(
    monkeypatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    url = f"sqlite+aiosqlite:///{tmp_path / 'production-seed.db'}"
    settings = SimpleNamespace(
        database_url=url,
        environment=Environment.PRODUCTION,
        deployment_stage=DeploymentStage.PRODUCTION,
        climate_demo_seed_enabled=True,
        climate_demo_publication_allowed=False,
    )
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



def test_climate_demo_publication_requires_explicit_staging_or_local_opt_in() -> None:
    local = Settings(
        environment=Environment.DEVELOPMENT,
        deployment_stage=DeploymentStage.DEVELOPMENT,
        climate_demo_seed_enabled=True,
    )
    staging = Settings(
        environment=Environment.PRODUCTION,
        deployment_stage=DeploymentStage.STAGING,
        climate_demo_seed_enabled=True,
        database_url="postgresql+asyncpg://demo:demo@localhost:5432/demo",
        jwt_secret_key=SecretStr("x" * 48),
        public_base_url="https://nextgenforearth.org",
        debug=False,
    )
    production = Settings(
        environment=Environment.PRODUCTION,
        deployment_stage=DeploymentStage.PRODUCTION,
        climate_demo_seed_enabled=True,
        database_url="postgresql+asyncpg://demo:demo@localhost:5432/demo",
        jwt_secret_key=SecretStr("x" * 48),
        public_base_url="https://nextgenforearth.org",
        debug=False,
    )
    disabled = Settings(
        environment=Environment.PRODUCTION,
        deployment_stage=DeploymentStage.STAGING,
        climate_demo_seed_enabled=False,
        database_url="postgresql+asyncpg://demo:demo@localhost:5432/demo",
        jwt_secret_key=SecretStr("x" * 48),
        public_base_url="https://nextgenforearth.org",
        debug=False,
    )

    assert local.climate_demo_publication_allowed is True
    assert staging.climate_demo_publication_allowed is True
    assert production.climate_demo_publication_allowed is False
    assert disabled.climate_demo_publication_allowed is False


