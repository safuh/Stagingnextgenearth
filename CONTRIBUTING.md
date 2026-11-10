# Contributing to Stagingnextgenearth

Thank you for contributing. Stagingnextgenearth is intended to become reusable infrastructure, so compatibility, documentation, and tests are as important as implementation.

## Development

Use **uv** as the canonical dependency and environment manager.

```bash
uv sync --extra dev
make check
```

For the individual quality gates:

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

For the reference application:

```bash
make run
make prod
```

For the Docker smoke contract:

```bash
make docker-test
```

## Pull requests

Every pull request should:

1. explain the problem and proposed design;
2. include tests for changed behavior;
3. update module documentation when boundaries or public behavior change;
4. update `docs/MILESTONES.md` when milestone status changes;
5. avoid unrelated refactors; and
6. leave CI green.

Security-sensitive changes require additional tests and documentation. Do not disclose vulnerabilities through normal public issues; follow `SECURITY.md`.

## Architecture changes

If a change affects dependency direction, public API, authentication, persistence semantics, deployment behavior, or another major architectural decision, add or update an ADR under `docs/architecture/adr/`.

## Database changes

Never edit an already-applied Alembic revision. Create a new revision and verify both upgrade and downgrade paths against PostgreSQL before opening a pull request.

```bash
uv run alembic revision -m "describe schema change"
uv run alembic upgrade head
```

Application processes must not run migrations automatically at startup. Treat migrations as an explicit release operation.

## Branch and commit discipline

Keep `main` clean and work from feature branches. Before opening or updating a pull request:

```bash
git fetch origin
git rebase origin/main
make check
git push --force-with-lease origin feat/my-change
```

Use `--force-with-lease`, never plain `--force`, after rebasing a private feature branch. Do not rebase a shared branch unless everyone using it agrees.

Use concise conventional commit-style messages such as:

```text
feat: add refresh token rotation
fix: dispose engine on shutdown
refactor: isolate repository contract
```

Do not claim a milestone complete until its acceptance criteria have been verified.
