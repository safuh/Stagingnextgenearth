.PHONY: install test lint typecheck check run prod migrate migrate-up migrate-down migrate-current migrate-history docker-up docker-down docker-test docker-prod

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

check: lint typecheck test

run:
	uv run uvicorn stagingnextgenearth.app:create_app --factory --reload --host 127.0.0.1 --port 8000

prod:
	uv run uvicorn stagingnextgenearth.app:create_app --factory --host 0.0.0.0 --port 8000

migrate: migrate-up

migrate-up:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

migrate-current:
	uv run alembic current

migrate-history:
	uv run alembic history

docker-up:
	docker compose -f docker/compose.yml up --build -d

docker-down:
	docker compose -f docker/compose.yml down

docker-test:
	bash scripts/docker-smoke.sh

docker-prod:
	bash scripts/docker-production.sh
