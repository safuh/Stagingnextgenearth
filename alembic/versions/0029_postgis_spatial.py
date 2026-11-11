"""Add PostGIS point geometry and spatial index for climate observations.

Revision ID: 0029_postgis_spatial
Revises: 0028_programme_planning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_postgis_spatial"
down_revision: str | None = "0028_programme_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        "ALTER TABLE climate_observations "
        "ADD COLUMN location geometry(Point, 4326)"
    )
    op.execute(
        "UPDATE climate_observations "
        "SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) "
        "WHERE location IS NULL"
    )
    op.create_index(
        "ix_climate_observations_location_gist",
        "climate_observations",
        ["location"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index(
        "ix_climate_observations_location_gist",
        table_name="climate_observations",
    )
    op.drop_column("climate_observations", "location")
