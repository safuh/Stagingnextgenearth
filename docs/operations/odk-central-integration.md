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
