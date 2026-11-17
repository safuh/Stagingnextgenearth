# Research protocol and ethics governance

Research studies use immutable, numbered protocol versions. Authors create a draft and submit it for independent review; reviewers record an append-only decision. A revision is a new protocol version rather than an edit to an existing submission. Ethics decisions are recorded separately and must reference an approved protocol version.

## Bounded history endpoints

All history reads require active organisation membership and access to the requested study:

- `GET /api/organizations/{organization_id}/research-studies/{study_id}/protocol-versions?limit=50&offset=0`
- `GET /api/organizations/{organization_id}/research-studies/{study_id}/protocol-versions/{protocol_id}/reviews?limit=50&offset=0`
- `GET /api/organizations/{organization_id}/research-studies/{study_id}/ethics-reviews?limit=50&offset=0`

Each endpoint accepts `limit` from 1 through 100 (default 50) and `offset` from 0 through 10,000 (default 0). Invalid bounds return HTTP 422. Ordering is deterministic: protocol versions are newest first by version number and identifier; review events are oldest first by review timestamp and identifier. Clients should request subsequent pages by increasing `offset` by the number of records returned.

Review history is append-only. Pagination limits response size and database work; it does not change review permissions or expose reviewer account identifiers. Evidence-ledger governance summaries remain metadata-only and do not include protocol content or private review notes.

## Study lifecycle

The organisation-level lifecycle endpoint is `PATCH /api/organizations/{organization_id}/research-studies/{study_id}/status`. It is restricted to organisation administrators, founders, executives and programme managers. Transitions are sequential: `concept → protocol → active → completed → published → archived`. Skipped, repeated and reverse transitions return HTTP 409.

The transition to `protocol` requires the latest protocol version to be approved by an independent reviewer. The transition to `active` additionally requires an approved or exempt ethics decision linked to that exact protocol version. The transition to `published` requires at least one linked publication record. Each successful transition writes an append-only `research.study.status_changed` organisation audit event in the same transaction as the study update.

The researcher workspace study registry exposes the next lifecycle action to authorised organisation managers. Failed gate checks are returned from the API and shown in the workspace; a successful action refreshes the study state and invalidates any previously loaded evidence snapshot so the next ledger reflects the new lifecycle.

## Researcher workspace workflow

Open **Manage protocol & ethics** on a study in the Research workspace to inspect its immutable protocol versions, review history and ethics decisions. Study leads and organisation administrators, founders and executives can create protocol drafts; the author submits a draft for independent review. Organisation reviewers who are not the study lead or protocol author can approve, reject or request revisions with a required review note. An approved protocol can then be selected for a formal ethics decision (approved, exempt, revisions required or rejected), with a committee reference and rationale. The workspace refreshes protocol and ethics history after a review and resets the selected governance records when the active organisation changes.

The interface does not bypass the API's independent-review checks. A reviewer who authored the protocol or leads the study cannot approve that protocol or record its ethics decision. A successful ethics decision is linked to the exact approved protocol version; the study lifecycle API checks that link before allowing activation.

## Governance audit events

Protocol version creation, submission, independent review and formal ethics decisions each append an organisation audit event in the same database transaction as the governance record. Events identify the actor and relevant study/protocol metadata; review notes and protocol contents are deliberately excluded from the audit payload. Organisation audit history remains tenant-scoped and available to founders, executives and administrators through `GET /api/organizations/{organization_id}/audit-events`.

## Research governance audit workspace

Founders, executives and administrators can load `GET /api/organizations/{organization_id}/research-governance/audit-events` from the Research workspace. The endpoint returns only research protocol, ethics and study lifecycle events, in newest-first order, with a page size of at most 200 and an offset capped at 100,000. The workspace presents 100 records per page and supports previous/next navigation. It excludes protocol content and review notes. Access is tenant-scoped and limited to organisation leadership.

## Governance audit CSV export

Founders, executives and administrators can export `GET /api/organizations/{organization_id}/research-governance/audit-events/export`. The export is tenant-scoped, newest-first and capped at 5,000 records. `X-Records-Truncated` indicates whether additional events were omitted. CSV cells beginning with spreadsheet formula characters are neutralised, and the file is UTF-8 with BOM for spreadsheet compatibility. Only audit metadata is exported; protocol contents and review notes are excluded.
