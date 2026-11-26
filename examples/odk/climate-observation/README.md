# NextGen For Earth — ODK climate observation demo

This directory contains a synthetic XLSForm and two synthetic OData-shaped submissions. It contains no real respondent information and must not be used as a production field form without programme and research review.

## Form contract

Upload the XLSForm to a dedicated ODK Central project. The field names intentionally match the NextGen climate evidence mapping:

| NextGen field | ODK field |
| --- | --- |
| Observation timestamp | observed_at |
| Climate variable | measurement |
| Numeric reading | value |
| Unit | unit |
| Latitude (WGS84) | latitude |
| Longitude (WGS84) | longitude |

Central supplies the ODK submission identifier as __id. The form also captures a non-personal site_code. It deliberately does not ask for respondent names, email addresses or phone numbers. Coordinates are decimal degrees and range-validated. The optional quality_note warns against entering personal information.

## Local Central acceptance

1. Start local Central with scripts/setup_odk_central_local.sh and bootstrap its local administrator with scripts/bootstrap_odk_central_local_admin.sh. This uses the local-only odk-admin@example.test login and needs no work mailbox.
2. Sign in at https://local:8443, create a project named NextGen Climate Demo, and upload nextgen_climate_observation.xlsx.
3. Preview the draft. Check date/time, measurement, unit and coordinate questions. Publish only after the preview is accepted.
4. Create a dedicated Central Web User for NextGen. Assign only project-level read permissions needed to list the form and read submissions (use the least-privilege viewer role available in the installed Central version). Do not use the Central system administrator as the integration identity.
5. Create an App User only if an ODK Collect device needs to download and submit the form. The NextGen sync worker authenticates as the dedicated Web User, not an App User.
6. In NextGen, configure base URL https://local:8443, the numeric project ID, the dedicated Web User credentials, and ODK_TLS_VERIFY=false in local development only. Keep ODK_TLS_VERIFY=true elsewhere.
7. Add this form mapping:

    {
      "nextgen_climate_observation": {
        "observed_at": "observed_at",
        "variable": "measurement",
        "value": "value",
        "unit": "unit",
        "latitude": "latitude",
        "longitude": "longitude"
      }
    }

8. Submit two synthetic records through Central's web form or ODK Collect. Run one ODK sync and confirm the observations appear in the organisation climate evidence ledger with pending review status.
9. Run sync again. Confirm the imported count does not increase and the duplicate count does. Confirm invalid timestamps or coordinates are rejected rather than silently accepted.
10. Confirm the ODK operations view reports a recent successful sync. Revoke the integration user's project access and verify a subsequent sync reports an authentication or permission failure without exposing credentials or submission bodies in logs.

## Offline fixture

sample_odata_submissions.json illustrates the OData row shape consumed by the worker. These are synthetic fixtures, not records uploaded to Central. Use them for tests and demonstrations only. Central's real submission feed remains the authority for live acceptance.

## Acceptance boundary

The XLSForm structure and fixture are reproducible repository assets. They do not prove Docker can pull and run Central on a particular workstation, that a live project exists, or that Central permissions and OData responses work in the target deployment. Mark live acceptance complete only after the full local sequence above succeeds. Hosted/staging acceptance is separate and requires trusted TLS, an operational email service and an approved non-production Central project.
