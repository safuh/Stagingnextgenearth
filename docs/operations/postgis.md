# PostgreSQL/PostGIS deployment

The production database target is PostgreSQL 17 with PostGIS 3.5. The
application remains compatible with SQLite for unit tests and lightweight
local development; spatial queries and the PostGIS geometry column are
PostgreSQL-only.

## Provision the database

Set the following in a protected deployment environment (use a strong,
unique password and do not commit the environment file):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT` (optional; defaults to 5432)

Start the database:

```bash
docker compose -f docker/compose.postgis.yml up -d postgres
docker compose -f docker/compose.postgis.yml ps
docker compose -f docker/compose.postgis.yml logs --tail=100 postgres
```

Configure the API's `DATABASE_URL` to use the same database and credentials,
for example `postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME`. The host
must be reachable from the API deployment; use the service DNS name
`postgres` when both services share a Compose network.

## Apply schema migrations

Run migrations once as a release operation, not from every API worker:

```bash
uv run alembic upgrade head
```

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
