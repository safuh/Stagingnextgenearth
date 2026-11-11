# Institutional partner reporting

The Next.js route `/workspace/partner` is available to active
`institutional_partner` members. The browser reads programme summaries and
then requests the dedicated endpoint:

`GET /organizations/{organization_id}/programmes/{programme_id}/partner-reporting`

The API enforces the institutional-partner role independently of the UI and
scopes every query to the active membership's organisation and the requested
programme. Other member roles receive HTTP 403; unknown or cross-tenant
programmes return HTTP 404.

## Data minimisation

The response includes programme status, indicator definitions and latest
measurement values, plus aggregate participation category, count and reporting
period. It deliberately excludes reporter identities, notes, evidence
references, group names, activity IDs and individual participant records.

Participation records below the fixed minimum disclosure threshold of five
participants are suppressed. This threshold is a basic disclosure control,
not a guarantee against inference when external information or overlapping
reports are available. Programme owners should avoid publishing overlapping
small-cohort totals.

Indicator progress is presented as a transparent arithmetic ratio against the
configured baseline and target. It is not an independent impact evaluation.
All measurements remain programme-reported and require separate verification.

## Operational boundary

The endpoint is read-only. It does not grant access to learner records,
volunteer applications, research datasets or climate observation source data.
The existing broader member reporting endpoints retain their own authorization
and are not used by this partner portal.
