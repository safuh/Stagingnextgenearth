# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.13 AS builder
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

COPY --from=builder /uv /uvx /bin/

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app

COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

COPY src ./src
COPY alembic ./alembic
COPY scripts ./scripts

RUN uv sync --locked --no-dev --no-editable \
    # CHIRPS area extraction decodes provider GeoTIFF rasters at runtime. Keep the
    # geospatial binary pinned separately from the base application lock set.
    && uv pip install --python /app/.venv/bin/python "rasterio==1.4.3" \
    && chown -R app:app /app

USER app
EXPOSE 10000

# Run migrations in the actual release container, using the exact installed
# environment and DATABASE_URL that the application will use.
CMD ["/bin/sh", "-c", "alembic upgrade head && python scripts/seed_nextgen_demo.py --organization-slug next-gen-for-earth-demo && exec uvicorn stagingnextgenearth.app:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
