# PostgreSQL/PostGIS deployment

The production database target is PostgreSQL 17 with PostGIS 3.5. The
application remains compatible with SQLite for unit tests and lightweight
local development; the PostGIS geometry column and spatial queries are
PostgreSQL-only.

## Configuration

Set the following in a protected deployment environment (use a strong,
unique password and do not commit the environment file):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT` (optional; defaults to 5432)
- `DATABASE_URL`, using the same credentials and the Compose service hostname
  `postgres`, for example
  `postgresql+asyncpg://USER:PASSWORD@postgres:5432/DBNAME`.

The API and database must share the Compose network. The commands below merge
the PostGIS database service with the production API definition, creating one
network and one deployment project.

## Deploy

Validate the merged production stack and start the database:

```bash
docker compose -f docker/compose.postgis.yml -f docker/compose.production.yml config --quiet
docker compose -f docker/compose.postgis.yml -f docker/compose.production.yml up -d postgres
docker compose -f docker/compose.postgis.yml -f docker/compose.production.yml ps
```

Wait until the database health check reports healthy, then apply migrations
once as a release operation:

```bash
docker compose -f docker/compose.postgis.yml -f docker/compose.production.yml run --rm api alembic upgrade head
docker compose -f docker/compose.postgis.yml -f docker/compose.production.yml up -d api
```

If malware scanning is configured, add `--profile scanning` to the production
Compose commands and start the `dataset-scanner` service alongside the API.
Migrations are never run automatically by API or worker processes.

Migration `0029_postgis_spatial` enables the PostGIS extension, adds an SRID
4326 point geometry to climate observations, backfills existing latitude and
longitude values, and creates a GiST index. Existing coordinate columns remain
the canonical API representation and preserve SQLite compatibility. The
migration is intentionally a no-op on non-PostgreSQL dialects.

## Operations and recovery

Persist the named `postgis-data` volume. Back up PostgreSQL with
`pg_dump`/managed database backups and test restores into an isolated
PostgreSQL/PostGIS instance before production use. A volume is not a backup.
Monitor database health, disk capacity, connection saturation, replication
(if configured), and backup age. Restrict database network access to
application and operator networks; do not expose PostgreSQL publicly.

Before upgrading PostGIS or PostgreSQL major versions, take and verify a
backup, test the upgrade against a restored copy, and schedule the required
maintenance window. Keep the PostGIS image pinned to a tested major/minor
series rather than using `latest`.
