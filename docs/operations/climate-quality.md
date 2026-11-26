# Climate quality and missing-data reporting

The climate API keeps ingestion, screening and independent review separate.
Provider ingestion creates observations in `pending` status. Unit conversion
preserves source values and units in `metadata_json.normalization`; screening
flags are stored in `metadata_json.quality_screening_flags`. A screening flag
is a prompt for review, not proof that a measurement is wrong. Verification
remains an independent reviewer decision.

## Screening report

`GET /api/organizations/{organization_id}/climate-observations/flagged`

Optional query parameters:

- `flag`: return only observations containing this exact flag.
- `quality_status`: `pending`, `verified` or `rejected`.
- `start` and `end`: timezone-aware timestamps; end is exclusive.
- `offset` and `limit`: pagination (maximum page size 200).

The report evaluates at most 5,000 newest matching rows so JSON screening
metadata can be handled consistently on SQLite and PostgreSQL. It returns
`scan_truncated=true` when more rows were available. In that case, the result
is a bounded report, not an exhaustive count; narrow the time range or status
filter before drawing conclusions. Arbitrary provider metadata is not returned.

## Daily station coverage

`GET /api/organizations/{organization_id}/climate-observations/coverage`

Required query parameters:

- `variable`
- `latitude` and `longitude` (WGS84)
- `start_date` and `end_date` (inclusive ISO calendar dates)

The endpoint reports expected days, days with at least one non-rejected
observation, missing dates and a coverage ratio. A station match uses a
coordinate tolerance of 0.0001 degrees. Windows are limited to 366 days.

**Missing-data policy: report only; never impute.** Missing dates are reported
as missing. The API does not synthesize observations, interpolate values,
carry values forward or treat a missing measurement as zero. Multiple
observations on one date count as one covered day. Rejected observations do
not satisfy coverage; pending and verified observations do. Consumers must
retain the quality status when interpreting coverage.

## Interpretation and limitations

- Canonical unit conversion is performed only for explicitly supported
  variable/unit pairs. Unsupported pairs retain their original value and unit
  and receive an `unsupported_unit` flag.
- Broad physical-range screening is deliberately conservative and is not a
  local-climatology test, instrument calibration, outlier model or scientific
  validation.
- Provider data may have different spatial resolutions, temporal conventions,
  uncertainty and provenance. Compare only after accounting for those
  differences.
- Coverage describes observation presence, not data quality, representativeness
  or completeness of the underlying environmental process.
- Configure domain-specific thresholds and review procedures with qualified
  climate researchers before using the outputs for research conclusions.


## Independent review and audit history

A reviewer with an active `admin` or `programme_manager` membership may
submit one decision for a pending observation:

`POST /api/organizations/{organization_id}/climate-observations/{observation_id}/review`

The request contains `decision` (`verified` or `rejected`) and an optional
review note. Submitters cannot review their own observations. A second review
decision is rejected with HTTP 409; corrections must use a separately governed
follow-up process rather than rewriting the original decision.

Each successful decision and its organisation audit event are committed in
the same database transaction. The audit event records the reviewer, submitting
user, observation identifier, decision, source, variable, observation timestamp
and review note. The event is append-only through the application API.

Authorised climate reviewers can retrieve the bounded audit history with:

`GET /api/organizations/{organization_id}/climate-observations/{observation_id}/review-history`

The response is tenant-scoped and ordered oldest first. This history is a
governance record; it does not independently validate the measurement or
replace source documents, calibration records or research methods.
