# Docker

## Production image

The production image installs application dependencies from the committed `uv.lock` file.

The Docker build uses `uv sync --locked --no-dev --no-editable`, so a stale lockfile fails the image build instead of silently resolving a different dependency graph.

The final image contains only the runtime environment and application source. Development dependencies are excluded, and the application runs as the non-root `app` user.

## One-command production deployment

The repository provides a reference production deployment path through Docker Compose. It does not store production credentials in the repository or image.

1. Export a production PostgreSQL asyncpg URL:

   ```bash
   export DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE'
   ```

2. Optionally set `APP_PORT` (default `8000`), `APP_NAME`, `APP_VERSION`, `LOG_LEVEL`, or the CORS settings.

3. Run:

   ```bash
   make docker-prod
   ```

The deployment command builds the locked production image, runs `alembic upgrade head` as an explicit one-shot migration operation, starts the API with restart protection, and waits for the readiness endpoint before reporting success. Readiness verifies that application startup completed and that the configured database is reachable.

Migrations are deliberately not part of the API container startup command. This keeps schema changes an explicit deployment operation while still providing a single reference command for the complete release sequence.

If readiness is not reached within the wait window, the script exits non-zero and prints the Compose service state for diagnosis. It does not tear down the existing deployment automatically.

### Production configuration

`docker/compose.production.yml` requires `DATABASE_URL` and forces `ENVIRONMENT=production` and `LOG_JSON=true`. The production `Settings` validation therefore requires a PostgreSQL `asyncpg` URL and disables debug mode.

The reference deployment uses an externally managed PostgreSQL database. Database credentials and other production secrets must be supplied through the deployment environment or secret-management system; they must never be committed to Compose files, Dockerfiles, or image layers.

Authentication remains an application composition concern. Consumers that enable the database-backed authentication composition must continue to provide their JWT secret and token lifetimes explicitly at the application composition root.

## Development Compose

For the local PostgreSQL-backed development environment, use:

```bash
make docker-up
```

and tear it down with:

```bash
make docker-down
```

The development stack intentionally contains local database credentials and should not be reused as a production configuration.
