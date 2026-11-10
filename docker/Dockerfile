# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.13 AS builder
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /uv /uvx /bin/

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app

COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

COPY src ./src
COPY alembic ./alembic

RUN uv sync --locked --no-dev --no-editable \
    && chown -R app:app /app

USER app
EXPOSE 8000

CMD ["uvicorn", "stagingnextgenearth.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
