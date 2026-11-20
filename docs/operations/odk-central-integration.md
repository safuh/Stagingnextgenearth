# ODK Central integration

The platform exposes a tenant-scoped import endpoint for ODK Central JSON submission pages:

`POST /api/organizations/{organization_id}/odk/imports`

A request contains `form_id`, a `mapping` from ODK field names to `observed_at`, `variable`, `value`, `unit`, `latitude`, and `longitude`, and a bounded `submissions` array (1–100 items). Optional `project_id` and `study_id` mappings link observations to existing records in the same organisation. ODK instance IDs are read from `instanceId`, `instanceID`, `__id`, or `meta/instanceID` and combined with the form ID for idempotency.

Example mapping:

```json
{
  "form_id": "community-rainfall-v1",
  "mapping": {
    "observed_at": "date_observed",
    "variable": "measurement",
    "value": "reading",
    "unit": "units",
    "latitude": "gps_lat",
    "longitude": "gps_lon"
  },
  "submissions": [
    {
      "instanceId": "uuid:field-0001",
      "data": {
        "date_observed": "2026-11-18T08:30:00+03:00",
        "measurement": "precipitation",
        "reading": 14.75,
        "units": "mm",
        "gps_lat": -0.681,
        "gps_lon": 34.767
      }
    }
  ]
}
```

Administrators, founders, executives, researchers and programme managers with active membership can use the import bridge. The endpoint accepts submission data, never an arbitrary URL or upstream credential. The scheduled worker reads mapped forms directly from Central's OData feed and uses the same climate evidence validation rules. Raw submission payloads are not retained. Only explicitly mapped climate fields and ODK form/instance identifiers enter the climate ledger. Every imported observation starts as `pending` and must pass the existing independent climate review workflow before it is treated as verified.

`GET /api/organizations/{organization_id}/odk/status` returns tenant-scoped imported and pending-review counts. Duplicate form/instance pairs are skipped on repeat imports.

## Secure Central connection management

An organisation administrator, founder, or executive can configure one Central project connection using:

- `PUT /api/organizations/{organization_id}/odk/connection`
- `GET /api/organizations/{organization_id}/odk/connection` (returns metadata only)
- `POST /api/organizations/{organization_id}/odk/connection/test`
- `GET /api/organizations/{organization_id}/odk/forms`
- `DELETE /api/organizations/{organization_id}/odk/connection`

The Central server URL must be HTTPS (localhost HTTP is allowed for development). The account password is encrypted at rest with Fernet and is never included in API responses. Set `ODK_ENCRYPTION_KEY` to a unique Fernet key in each environment. Generate one with:

```bash
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep the key in the deployment secret manager and back it up securely. Losing or rotating this key without re-encrypting stored connection credentials makes those credentials unreadable; re-enter the Central password after a key loss. Use a dedicated, least-privilege Central account for the integration, not a personal administrator account. Central session authentication uses `POST /v1/sessions` followed by a Bearer token for project form discovery, as documented by ODK: https://docs.getodk.org/central-api-authentication/.

The API connection test verifies credentials and project access; it does not start the worker. The automated worker must be started separately in the target environment.

## Automated synchronisation

The `odk-sync` worker authenticates to Central using the saved organisation credentials, checks the configured project forms, and polls the OData `Submissions` feed for each form with a mapping. It follows Central's `@odata.nextLink` only when the link remains on the configured Central origin, processes pages of 100, and caps each form at 10 pages per poll. Per-form continuation cursors are persisted between runs, so larger forms progress across polls; after reaching the end, the next poll starts from the first page to discover new submissions. The organisation/form/instance uniqueness key makes repeated imports idempotent. Imported observations remain `pending` until independently reviewed.

The worker writes durable run history. Inspect it with `GET /api/organizations/{organization_id}/odk/sync-runs`; the connection summary also reports the last run state. Status values are `succeeded`, `partial`, and `failed`. Error summaries contain form identifiers and exception classes, not submission contents or credentials.

Start locally after configuring `ODK_ENCRYPTION_KEY` and at least one connection/mapping:

```bash
uv run python -m stagingnextgenearth.workers.run_odk_sync --poll-interval-seconds 60 --batch-size 10
# Or, with Compose:
docker compose --profile odk -f docker/compose.yml up -d odk-sync
```

Production Compose exposes the worker under the `odk` profile:

```bash
docker compose --profile odk -f docker/compose.production.yml up -d odk-sync
```

Run a single ODK sync worker replica for now. The database uniqueness constraint protects against duplicate observation records; a distributed lease/queue is required before horizontally scaling the poller. Central pagination is bounded to 1,000 submissions per configured form per poll; continuation cursors are persisted so the next poll resumes where the previous bounded run stopped. Once a form feed is exhausted, the next run starts at the beginning to discover newly submitted records and safely skips prior imports. Configure ODK Central account permissions to read only the required project and forms.

## Operational alerts and worker health

Organisation administrators, founders and executives can inspect the manager-only operational summary at:

`GET /api/organizations/{organization_id}/odk/operations`

The research workspace displays the returned alerts alongside the durable run history. The current checks are:

- `sync_not_started`: an enabled connection has not completed its first run.
- `worker_stale`: an enabled connection has not completed a run in five minutes.
- `stale_pagination_cursor`: a saved continuation cursor has remained without a completed sync for more than 15 minutes.
- `repeated_sync_failures`: the last three runs all reported errors.
- `central_credentials_rejected`: Central returned HTTP 401; verify or rotate the service account password.
- `central_project_access_denied`: Central returned HTTP 403; review project/form permissions.
- `connection_disabled`: the organisation has deliberately disabled the connection.

The worker also emits a warning for partial or failed runs. Error summaries classify HTTP 401, 403, 404, 410 and 429 responses without storing response bodies, request URLs, credentials or submission contents. These are dashboard/log alerts, not email or SMS notifications. Keep one worker replica until a distributed scheduler/lease and external alert delivery are implemented.

## Safe ODK encryption-key rotation

The rotation utility re-encrypts every saved connection password in one database transaction. It locks the connection rows, verifies that each credential decrypts with the old key, verifies the new ciphertext, and aborts without partial updates if any row cannot be decrypted. `--dry-run` performs the same verification without changing records.

**Do not rotate while API instances or the ODK worker are running.** Stop all API replicas and the `odk-sync` worker first so no process can write a credential using the old key during rotation. Take and verify a database backup, then supply the new key as `ODK_ENCRYPTION_KEY` and the existing key as `ODK_ENCRYPTION_KEY_OLD`:

```bash
export ODK_ENCRYPTION_KEY_OLD='<current-fernet-key>'
export ODK_ENCRYPTION_KEY='<new-fernet-key>'
uv run python -m stagingnextgenearth.workers.rotate_odk_key --dry-run
uv run python -m stagingnextgenearth.workers.rotate_odk_key
unset ODK_ENCRYPTION_KEY_OLD
```

For production Compose, run the same module as a one-off API container, passing the old key only to that process:

```bash
docker compose --env-file .env.production -f docker/compose.production.yml run --rm \
  -e ODK_ENCRYPTION_KEY_OLD="$ODK_ENCRYPTION_KEY_OLD" api \
  python -m stagingnextgenearth.workers.rotate_odk_key --dry-run
```

After the dry run succeeds, repeat without `--dry-run`. Update the deployment secret `ODK_ENCRYPTION_KEY` to the new key, remove the old key from the operator environment/secret store, restart the API and one ODK worker replica, test the Central connection, and confirm one successful sync. Retain the database backup and old key in the approved recovery vault until post-rotation verification and the organisation's retention policy allow disposal. Never put either key in source control, command history, application logs or support tickets. If the old key has already been lost, re-enter each Central password through the connection settings; encrypted credentials cannot be recovered without their original key.

## Local Central test environment without a work email

A work mailbox is **not required** to create a local Central administrator. Central's documented command-line account creation flow accepts an email-shaped login and sets the password interactively; it does not need to send an invitation or password-reset email. Use the reserved, non-deliverable address `odk-admin@example.test` for this local-only account. Do not use it for a hosted or production Central deployment.

The repository includes two helpers that clone the official ODK Central stable branch into an ignored local directory, configure a self-signed local instance bound only to loopback on ports 8088/8443, and create/promote the local administrator:

```bash
./scripts/setup_odk_central_local.sh
# Add this entry to /etc/hosts if the name does not resolve:
# 127.0.0.1 local
./scripts/bootstrap_odk_central_local_admin.sh
```

The first command uses Docker Compose and can take several minutes to build and start Central. Wait for its `nginx` service to become healthy. Then open `https://local:8443`, accept the self-signed certificate warning for this local development instance, and sign in using `odk-admin@example.test` plus the password entered during bootstrap. The local Central checkout, configuration, and database files live under `.local/odk-central/` and are excluded from Git.

For the NextGen API/worker to call this self-signed local instance, set `ODK_TLS_VERIFY=false` in the **development-only** NextGen environment and use `https://local:8443` as the Central base URL. The application only permits this override for loopback/local hostnames, and production configuration rejects it. Keep `ODK_TLS_VERIFY=true` in staging and production. Generate `ODK_ENCRYPTION_KEY` separately for the NextGen environment; it is unrelated to Central's administrator password.

Create a separate Central user for the NextGen integration after signing in, grant it only the project/form permissions needed to read the test submissions, and use that account in the NextGen ODK connection form. The initial administrator is for local setup only. Use synthetic submissions and a dedicated non-production project. No messages are sent to `example.test`, and no real work email is needed for this local acceptance path.

To stop the local Central stack without deleting its database:

```bash
cd .local/odk-central && docker compose stop
```

To start it again:

```bash
cd .local/odk-central && docker compose up -d
```

This self-signed local setup is not a production deployment pattern. Public Central requires a real domain, trusted TLS, and an operational email service for account verification and recovery.

## Offline acceptance when no Central test project is available

A live Central account is not required for local development or CI. The protocol-level ODK client tests use HTTPX `MockTransport` and exercise the actual HTTP client implementation without network access or real credentials. They verify session creation, bearer-token use, form discovery, OData pagination, session revocation, and rejection of cross-origin pagination links. The worker tests separately verify mapped import, idempotency, bounded pagination, error classification, operational status and encryption-key rotation.

Run the offline acceptance suite:

```bash
uv run pytest -q \
  tests/test_odk_central_client.py \
  tests/test_odk_sync_worker.py \
  tests/test_odk_connections_api.py \
  tests/test_odk_key_rotation.py
```

These tests establish local protocol and application behaviour; they do **not** prove that a particular Central deployment, account, project, form or permission set is configured correctly. Keep live Central acceptance marked pending until the organisation has access to a dedicated non-production project. When that becomes available, use a least-privilege account, a synthetic form and non-sensitive sample submissions, then verify connection test, form discovery, one bounded sync, duplicate suppression and credential revocation. Never use production field submissions as test fixtures.

## Synthetic climate-observation form and local acceptance

A ready-to-upload synthetic XLSForm, two OData-shaped fixture records, field mapping and end-to-end local acceptance procedure are maintained in examples/odk/climate-observation/README.md. The form uses the field names expected by the sync mapping and avoids respondent identity fields.

Validate the checked-in assets with:

    python scripts/validate_odk_climate_demo.py

Follow the README for draft preview/publication, least-privilege integration identity, field mapping, sync, duplicate suppression, pending review and credential-revocation checks. The fixture is not a substitute for a live Central submission.


## Row-level import validation and diagnostics

The scheduled sync validates each submission inside its own database savepoint. A malformed row is rejected without rolling back valid rows from the same OData page; the sync still advances the page cursor after successfully processing the page. The run history records imported, duplicate and rejected counts separately, and stores a bounded summary of validation reasons without recording submission bodies or credential material.

A rejected submission is not marked as imported. If it is corrected in Central and later returned by the feed with the same ODK instance ID, it can be imported on a later sync. Replaying already imported instance IDs remains idempotent.

### Source revisions and deletion provenance

The importer retains the ODK system metadata fields `updatedAt`, `reviewState`, and (where supported by the Central version) `deletedAt` in the observation's provenance metadata. When a previously imported instance is replayed with a changed `updatedAt`, the importer flags `odk_source_revision_detected`; it does not overwrite the measurement values or an existing `verified`/`rejected` decision. A source deletion is retained as `odk_source_deleted` with `odk_source_deletion_review_required`. Reviewers must reconcile these flags against the source record and study protocol. This is intentionally non-destructive: an upstream deletion is not, by itself, authority to erase an organisation's research evidence. Older Central versions that omit these system fields continue to sync, but cannot provide the corresponding lifecycle signal.

The organisation workspace exposes these notices in **Research → ODK Central → ODK reconciliation queue**. The API is also available to authorised organisation reviewers:

- `GET /api/organizations/{organization_id}/odk/reconciliation?limit=100` lists source-change notices (maximum 250), scoped to the active organisation. It returns identifiers and provenance only, never raw submissions.
- `POST /api/organizations/{organization_id}/odk/{observation_id}/reconciliation` accepts one of `acknowledge_revision`, `acknowledge_deletion`, or `retain_observation`, plus an optional review note. Each action clears only the corresponding review flag(s), stamps the reviewer/time, and appends an organisation audit event.

Acknowledge revision and deletion separately when both are pending. `retain_observation` is the explicit decision to keep the organisation's evidence record while acknowledging all outstanding source lifecycle notices. None of these actions deletes an observation, changes its measurement, or changes its independent climate-quality status. A second decision after all notices are cleared returns HTTP 409; records outside the organisation return 404. Only active members with an ODK import/research-management role can view or decide the queue.

### Transient Central API failures and bounded retries

The ODK client retries idempotent Central reads (form discovery and OData page retrieval) up to four total attempts when the network fails transiently or Central responds with HTTP 429, 500, 502, 503 or 504. It uses capped exponential backoff for transport/server failures and honours a numeric `Retry-After` value for rate limiting (capped at ten seconds per wait). Authentication, permission, missing-resource and expired-cursor responses are not blindly retried: they are surfaced to the sync worker for credential/access remediation or cursor recovery. Session creation is not automatically retried to avoid creating duplicate sessions. All retries remain bounded; a failed operation is recorded in the durable sync run and the saved page cursor is not advanced for a page that was not successfully processed.

### Expired continuation cursors

If Central rejects a saved OData continuation URL with HTTP 410, the worker clears only that form's saved cursor and records the run as failed/partial with a classified cursor-expiry diagnostic. It does not advance or discard any unprocessed page. The next scheduled run restarts that form from its first page; already imported instances are skipped by the organisation/form/instance idempotency key, and any new/corrected valid rows can be accepted. This recovery is deliberately performed on the next poll rather than looping indefinitely against an invalid continuation URL. The worker regression test verifies that a 410 clears the persisted cursor and that the following run restarts from the first page without duplicating evidence.
