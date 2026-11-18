.PHONY: install test lint typecheck check run prod migrate migrate-up migrate-down migrate-current migrate-history bootstrap docker-up docker-down docker-test docker-prod run-odk-sync web-check release-check

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

# Bootstrap depends on the schema being current. This is additive and never resets volumes.
bootstrap: migrate-up
	uv run python scripts/bootstrap_nextgen.py $(if $(MANIFEST),--manifest $(MANIFEST),)

run-odk-sync:
	uv run python -m stagingnextgenearth.workers.run_odk_sync --poll-interval-seconds 60

web-check:
	cd web && npm ci --no-audit --no-fund && npm run typecheck && npm run lint && npm test && npm run build

release-check: check web-check
	docker compose --env-file .env.production.example -f docker/compose.production.yml config --quiet
	docker compose --env-file .env.production.example --profile odk -f docker/compose.production.yml config --quiet
