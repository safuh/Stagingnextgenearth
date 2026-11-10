"""Persistence contract tests for the initial NextGen platform domain."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import User
from stagingnextgenearth.platform import (
    ClimateObservation,
    Membership,
    Organization,
    Programme,
    Project,
    ResearchStudy,
)


@pytest.mark.asyncio
async def test_platform_domain_tables_create_and_persist() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            user = User(identifier="researcher@example.org", password_hash="test-hash")
            session.add(user)
            await session.flush()

            organization = Organization(
                name="NextGen for Earth",
                slug="nextgen-for-earth",
                country_code="KE",
                owner_user_id=user.id,
            )
            session.add(organization)
            await session.flush()

            session.add(
                Membership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role="admin",
                    status="active",
                )
            )
            programme = Programme(
                organization_id=organization.id,
                title="Climate and Health Research",
                slug="climate-health-research",
                status="active",
                created_by=user.id,
            )
            session.add(programme)
            await session.flush()

            project = Project(
                organization_id=organization.id,
                programme_id=programme.id,
                title="Coastal climate-health study",
                country_code="KE",
                county="Kilifi",
                status="active",
                created_by=user.id,
            )
            session.add(project)
            await session.flush()

            study = ResearchStudy(
                organization_id=organization.id,
                project_id=project.id,
                title="Climate variability and community health",
                status="active",
                lead_researcher_id=user.id,
            )
            session.add(study)
            await session.flush()

            observation = ClimateObservation(
                organization_id=organization.id,
                study_id=study.id,
                project_id=project.id,
                observed_at=__import__("datetime").datetime(2026, 1, 1),
                variable="precipitation",
                value=24.5,
                unit="mm",
                latitude=-3.5107,
                longitude=39.9093,
                source="test-fixture",
                created_by=user.id,
            )
            session.add(observation)
            await session.commit()

            assert await session.scalar(select(Organization).where(
                Organization.slug == "nextgen-for-earth"
            )) is not None
            assert await session.scalar(select(Programme).where(
                Programme.slug == "climate-health-research"
            )) is not None
            assert await session.scalar(select(ResearchStudy).where(
                ResearchStudy.title == "Climate variability and community health"
            )) is not None
            assert await session.scalar(select(ClimateObservation).where(
                ClimateObservation.variable == "precipitation"
            )) is not None
    finally:
        await engine.dispose()
