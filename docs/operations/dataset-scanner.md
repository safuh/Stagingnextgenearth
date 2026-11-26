# Dataset scanner production runbook

The dataset scanner is a separate long-running process. It polls PostgreSQL for
quarantined dataset files, claims work using database row locks, streams object
bytes to ClamAV INSTREAM, and records each file's verdict independently. Run it
as a dedicated service; do not start it from the API application or from every
API worker.

## Prerequisites

- PostgreSQL reachable by both API and scanner.
- A private S3-compatible bucket reachable by both processes.
- A reachable ClamAV TCP service on a private, trusted network.
- The same application image/version and database schema for API and scanner.
- A secret manager or protected deployment environment for credentials.

The storage adapter currently uses explicit access-key credentials. It does not
yet support IAM/workload identity discovery or temporary session credentials.
The ClamAV TCP connection is not encrypted or authenticated by this adapter;
keep it on a private network.

## Configuration

Supply these variables to the production Compose deployment:

| Variable | Requirement | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Required | PostgreSQL connection used by API and worker |
| `OBJECT_STORAGE_ENABLED` | `true` | Enables private object storage |
| `OBJECT_STORAGE_BUCKET` | Required | Quarantine bucket |
| `OBJECT_STORAGE_REGION` | Optional | Defaults to `us-east-1` |
| `OBJECT_STORAGE_ENDPOINT_URL` | Optional | S3-compatible endpoint override |
| `OBJECT_STORAGE_ACCESS_KEY_ID` | Required | Storage credential |
| `OBJECT_STORAGE_SECRET_ACCESS_KEY` | Required | Storage credential |
| `MALWARE_SCANNING_ENABLED` | `true` | Enables scanner workflow |
| `CLAMAV_HOST` | Required | Private DNS name or address of ClamAV |
| `CLAMAV_PORT` | Optional | Defaults to `3310` |
| `CLAMAV_TIMEOUT_SECONDS` | Optional | Defaults to `30` |
| `DATASET_SCANNER_BATCH_SIZE` | Optional | Defaults to `10`, range 1–100 |
| `DATASET_SCANNER_POLL_INTERVAL_SECONDS` | Optional | Defaults to `5`, must be positive |

Use separate credentials per environment and grant the worker only the object
read permissions it needs. The API additionally needs its upload and download
permissions. Do not commit a populated environment file or place credentials
in the image.

## Deploy and operate

From the repository root, after configuring the deployment environment:

```bash
docker compose --profile scanning -f docker/compose.production.yml config
docker compose --profile scanning -f docker/compose.production.yml build api dataset-scanner
docker compose --profile scanning -f docker/compose.production.yml run --rm api alembic upgrade head
docker compose --profile scanning -f docker/compose.production.yml up -d api dataset-scanner
docker compose --profile scanning -f docker/compose.production.yml ps
```

Migrations are an explicit release step; they are not run automatically by
either service. Deploy compatible schema changes before starting application
versions that depend on them.

Inspect worker activity and failures:

```bash
docker compose --profile scanning -f docker/compose.production.yml logs --tail=200 dataset-scanner
docker compose --profile scanning -f docker/compose.production.yml logs -f dataset-scanner
docker compose --profile scanning -f docker/compose.production.yml restart dataset-scanner
```

The scanner service is in the opt-in `scanning` Compose profile, so a standard production `up` does not start a worker when malware scanning is not configured. Activate the profile only after configuring object storage and ClamAV. The process logs batch totals for scanned, rejected and failed files. A file
that cannot be retrieved or scanned remains quarantined; infrastructure errors
must not be interpreted as a clean verdict. Investigate persistent failures
through worker logs, database state and object-storage/ClamAV health. Do not
manually mark a file clean to clear a backlog.

## Capacity and availability

Start with one scanner replica and a modest batch size. Increase batch size
only after measuring ClamAV capacity, object-store throughput, database load
and scan latency. The worker's row-locking claim path is designed to prevent
two workers from processing the same claimed row; additional replicas can be
introduced after validating database connection limits and ClamAV capacity.
The poll interval controls idle polling frequency, not a guaranteed processing
latency.

The scanner has no HTTP health endpoint. Monitor container state, restart
count, logs, and the age/count of quarantined files using deployment-level
monitoring. Alert on sustained worker restarts, repeated scan failures, and a
growing quarantine backlog. Establish retention and incident procedures for
rejected files separately from normal dataset retention.

## Shutdown and recovery

The Compose service has a 30-second stop grace period and uses an init process
to forward signals and reap child processes. Allow graceful shutdown during
deployments. If a worker is terminated while processing a file, verify that
the file remains quarantined and is eligible for a later retry before
increasing replicas or changing database state.

Before production launch, test a clean file, a known EICAR test file in an
isolated test environment, ClamAV unavailability, object-store unavailability,
worker restart during a scan, and recovery after service restoration. Never
use live participant or sensitive research data for scanner acceptance tests.
