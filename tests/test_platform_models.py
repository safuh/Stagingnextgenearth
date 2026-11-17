"""Persistence contract tests for the initial NextGen platform domain."""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.api.dependencies import get_membership_roles, membership_has_any_role
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import User
from stagingnextgenearth.platform import (
    ClimateObservation,
    Membership,
    MembershipRole,
    Organization,
    Programme,
    ProgrammeDeliverable,
    Project,
    ResearchStudy,
)


@pytest.mark.asyncio
async def test_platform_domain_tables_create_and_persist() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

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

            membership = Membership(
                organization_id=organization.id,
                user_id=user.id,
                role="admin",
                status="active",
            )
            session.add(membership)
            await session.flush()
            session.add(
                MembershipRole(membership_id=membership.id, role="researcher")
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

            deliverable = ProgrammeDeliverable(
                organization_id=organization.id,
                programme_id=programme.id,
                title="Community climate baseline report",
                status="planned",
                assigned_to=user.id,
                created_by=user.id,
            )
            session.add(deliverable)
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

            session.add(
                ClimateObservation(
                    organization_id=organization.id,
                    study_id=study.id,
                    project_id=project.id,
                    observed_at=datetime(2026, 1, 1),
                    variable="precipitation",
                    value=24.5,
                    unit="mm",
                    latitude=-3.5107,
                    longitude=39.9093,
                    source="test-fixture",
                    created_by=user.id,
                )
            )
            await session.commit()

            assigned_role = await session.scalar(
                select(MembershipRole).where(
                    MembershipRole.membership_id == membership.id,
                    MembershipRole.role == "researcher",
                )
            )
            assert assigned_role is not None

            resolved_roles = await get_membership_roles(session, membership)
            assert resolved_roles == frozenset({"admin", "researcher"})
            assert await membership_has_any_role(
                session, membership, {"researcher"}
            )
            assert await membership_has_any_role(
                session, membership, {"admin"}
            )
            assert not await membership_has_any_role(
                session, membership, {"youth_volunteer"}
            )

            assert await session.scalar(
                select(Organization).where(Organization.slug == "nextgen-for-earth")
            ) is not None
            assert await session.scalar(
                select(Programme).where(Programme.slug == "climate-health-research")
            ) is not None
            stored_deliverable = await session.scalar(
                select(ProgrammeDeliverable).where(
                    ProgrammeDeliverable.id == deliverable.id
                )
            )
            assert stored_deliverable is not None
            assert stored_deliverable.status == "planned"
            assert stored_deliverable.assigned_to == user.id

            assert await session.scalar(
                select(ResearchStudy).where(
                    ResearchStudy.title == "Climate variability and community health"
                )
            ) is not None
            assert await session.scalar(
                select(ClimateObservation).where(
                    ClimateObservation.variable == "precipitation"
                )
            ) is not None
    finally:
        await engine.dispose()
