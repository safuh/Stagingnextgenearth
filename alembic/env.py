"""Alembic migration environment for the NextGen for Earth platform."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import RefreshToken, ResearcherProfile, User  # noqa: F401
from stagingnextgenearth.platform import (  # noqa: F401
    ClimateIngestionRun,
    ClimateObservation,
    Membership,
    Organization,
    Programme,
    Project,
    ResearchDatasetFile,
    ResearchDatasetFileAccessEvent,
    ResearchEthicsReviewEvent,
    ResearchProtocolReviewEvent,
    ResearchProtocolVersion,
    ResearchMilestone,
    ResearchProposalReviewEvent,
    ResearchStudyProposal,
    ResearchStudy,
    ResearchStudyCollaborator,
)

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
