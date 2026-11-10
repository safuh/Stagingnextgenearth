# Docker

The repository contains separate Docker Compose definitions for development and the reference production deployment path.

## Production image contract

- multi-stage build where useful;
- non-root runtime user;
- deterministic dependency installation from `uv.lock`;
- no development dependencies in production;
- process-level health endpoint;
- graceful container shutdown through the application process; and
- no secrets baked into image layers.

The production image is built by `docker/Dockerfile`. The reference production deployment is defined by `docker/compose.production.yml` and orchestrated by `scripts/docker-production.sh` / `make docker-prod`.

Production credentials are supplied externally. The production Compose definition requires `DATABASE_URL` and does not define database credentials or other secrets.
