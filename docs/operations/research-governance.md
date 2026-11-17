# Research protocol and ethics governance

Research studies use immutable, numbered protocol versions. Authors create a draft and submit it for independent review; reviewers record an append-only decision. A revision is a new protocol version rather than an edit to an existing submission. Ethics decisions are recorded separately and must reference an approved protocol version.

## Bounded history endpoints

All history reads require active organisation membership and access to the requested study:

- `GET /api/organizations/{organization_id}/research-studies/{study_id}/protocol-versions?limit=50&offset=0`
- `GET /api/organizations/{organization_id}/research-studies/{study_id}/protocol-versions/{protocol_id}/reviews?limit=50&offset=0`
- `GET /api/organizations/{organization_id}/research-studies/{study_id}/ethics-reviews?limit=50&offset=0`

Each endpoint accepts `limit` from 1 through 100 (default 50) and `offset` from 0 through 10,000 (default 0). Invalid bounds return HTTP 422. Ordering is deterministic: protocol versions are newest first by version number and identifier; review events are oldest first by review timestamp and identifier. Clients should request subsequent pages by increasing `offset` by the number of records returned.

Review history is append-only. Pagination limits response size and database work; it does not change review permissions or expose reviewer account identifiers. Evidence-ledger governance summaries remain metadata-only and do not include protocol content or private review notes.
