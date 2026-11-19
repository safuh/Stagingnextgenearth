# Funding and grant management

The funding workspace is an internal, tenant-scoped register for grant opportunities, awards, budgets and financial stewardship. It does not initiate, receive or move funds.

## Access and endpoints

Only active organisation administrators, founders and executives can read or change funding records. Every route is scoped by `organization_id`; linked opportunities, partners, programmes, awards and budget lines are checked against that same tenant.

- `GET/POST/PATCH /api/organizations/{organization_id}/funding/opportunities`
- `GET/POST/PATCH /api/organizations/{organization_id}/funding/awards`
- `GET/POST /api/organizations/{organization_id}/funding/awards/{award_id}/budget-lines`
- `GET/POST /api/organizations/{organization_id}/funding/awards/{award_id}/ledger`
- `GET /api/organizations/{organization_id}/funding/report`
- `GET /api/organizations/{organization_id}/funding/report.csv`
- `GET /api/organizations/{organization_id}/funding/audit-events`

## Financial records

Opportunities record donor/funder, expected amount, currency, deadline, reference and pursuit stage. Awards record the grant agreement, donor, amount, restrictions, programme/partner links, dates, status and reporting deadline. Budget lines allocate an award to named categories and optionally a programme. Pledges, commitments and expenditure are separate dated ledger entries. All monetary values use fixed-precision decimal amounts and an explicit ISO-style three-letter currency code; reports never add unlike currencies together.

The API rejects budget allocations above the award amount, expenditure above its budget line and expenditure above the award total. Award-row locking serialises budget and expenditure writes on PostgreSQL. Each created record emits an append-only funding audit event. CSV export is private/no-store and neutralises spreadsheet formula prefixes.

## Operational boundaries

This module is a register and reporting workspace, not an accounting ledger or banking system. It does not include payment gateways, checkout, card capture, bank-account connections, fund transfers, remittance, payment-provider APIs or automated disbursement. Pledges and commitments are recorded as organisational statements, not proof that money has cleared. Expenditure entries are user-entered records and require the organisation's separate finance controls and supporting documentation.

Before production use, finance owners must approve the chart of accounts, evidence/receipt retention, currency conversion policy (not yet provided by this module), approval thresholds, donor restrictions and reporting templates. Do not use the register as a substitute for statutory accounting records.
