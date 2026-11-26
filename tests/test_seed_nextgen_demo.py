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
from stagingnextgenearth.platform.models import (
    InstitutionalPartner,
    Organization,
    OrganizationPerson,
    Programme,
    PublicContentEntry,
)


def test_demo_seed_is_idempotent_and_keeps_unverified_records_private(
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

    async def inspect_seed() -> dict[str, int | bool]:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            people = list((await session.scalars(select(OrganizationPerson))).all())
            partners = list((await session.scalars(select(InstitutionalPartner))).all())
            content = list((await session.scalars(select(PublicContentEntry))).all())
            programmes = list((await session.scalars(select(Programme))).all())
            user_count = int(await session.scalar(select(func.count(User.id))) or 0)
            return {
                "people": len(people),
                "partners": len(partners),
                "content": len(content),
                "programmes": len(programmes),
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
    assert first["partners"] == len(seed_nextgen_demo.PARTNERS)
    assert first["content"] == len(seed_nextgen_demo.CONTENT) + len(seed_nextgen_demo.PUBLICATIONS) + len(seed_nextgen_demo.STORY)
    assert first["programmes"] == 4
    assert first["users"] == 1
    assert first["people_public_verified"] is True
    assert first["partners_public_unverified"] is True
    assert first["content_published"] is True
    assert first["programmes_planned"] is True
