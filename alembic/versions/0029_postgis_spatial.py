"""Add PostGIS point geometry and spatial index for climate observations.

Revision ID: 0029_postgis_spatial
Revises: 0028_programme_planning
"""

from collections.abc import Sequence
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
    op.execute(
        """
        CREATE FUNCTION sync_climate_observation_location()
        RETURNS trigger AS $
        BEGIN
            NEW.location := ST_SetSRID(
                ST_MakePoint(NEW.longitude, NEW.latitude), 4326
            );
            RETURN NEW;
        END;
        $ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_climate_observation_location
        BEFORE INSERT OR UPDATE OF latitude, longitude
        ON climate_observations
        FOR EACH ROW
        EXECUTE FUNCTION sync_climate_observation_location()
        """
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
    op.execute(
        "DROP TRIGGER IF EXISTS trg_climate_observation_location "
        "ON climate_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS sync_climate_observation_location()")
    op.drop_column("climate_observations", "location")
