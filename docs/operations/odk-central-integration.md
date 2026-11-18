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

Only administrators, researchers, and programme managers with active membership can import. The endpoint accepts submission data, never an arbitrary URL or upstream credential. ODK Central authentication, incremental pagination, retries, and scheduled polling must run in a trusted sync worker that calls this endpoint with the resulting JSON page; this milestone provides the validated ingestion bridge, not a background Central poller or webhook subscription. Raw submission payloads are not retained. Only explicitly mapped climate fields and ODK form/instance identifiers enter the climate ledger. Every imported observation starts as `pending` and must pass the existing independent climate review workflow before it is treated as verified.

`GET /api/organizations/{organization_id}/odk/status` returns tenant-scoped imported and pending-review counts. Duplicate form/instance pairs are skipped on repeat imports.
