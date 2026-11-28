# Organisation creation and first-run onboarding

## Purpose

Provide a consistent first-run workflow for creating an organisation tenant, establishing its first administrator, onboarding team members and starting governed research/programme work.

## Entry point

Authenticated workspace route: `/workspace/organisations/new`.

The route calls `POST /api/organizations`. The API creates the organisation, an active `admin` membership for the caller and an `organization.created` audit event in one database transaction. The unique organisation slug is validated by the API; HTTP 409 is shown as a correctable address conflict. The API remains the authority for all tenant and role checks.

## Create a tenant

Required fields:

- Organisation name (2–200 characters)
- Unique slug (2–120 lowercase letters/numbers separated by single hyphens)
- Country code (two-letter ISO-style code; default KE)
- Optional description (maximum 5,000 characters)

The browser suggests a slug from the organisation name, but the server validates it and enforces uniqueness. Do not treat a successful create response as proof of legal registration, mandate, tax status, safeguarding capacity or ethics approval.

## First-run checklist

1. Confirm the organisation name, country, mission and accountable owner.
2. Verify the organisation's legal identity and mandate using the relevant external evidence process.
3. Review the creator's active administrator membership and organisation-created audit event.
4. Invite each existing platform account individually through People and Access; choose least-privilege roles.
5. Have invitees accept their invitations and verify active membership.
6. Configure programme purpose, delivery owner, dates, geography and reporting definitions.
7. Create research studies in concept status; prepare protocol and data plans.
8. Obtain independent protocol and ethics approvals before human-participant fieldwork.
9. Register datasets with provenance, licence, sensitivity, permitted use and retention requirements.
10. Configure climate and learning workspaces only where they match the organisation's mandate and governance.

## Existing organisation invitations

An invitation is tied to an existing platform identity. Creating an organisation does not create user accounts for team members. The organisation administrator sends an invitation with an explicit role; the invitee authenticates and accepts before access becomes active. Role assignment, suspension and ownership transfer are separate audited operations.

## Research creation hand-off

Use `/workspace/research` with the newly created organisation selected. Create a study concept, assign the lead researcher and sponsor, and define objectives, methods, geography, participants, risks and intended outputs. A concept record is not authorisation to begin collection. Protocol review, ethics review, community permissions, data stewardship and publication approval remain distinct gates.

## Security and audit

- Organisation list APIs return only active memberships for the caller.
- All organisation writes use an organisation ID and server-side membership/role checks.
- Organisation creation and initial admin membership commit atomically with the `organization.created` audit event.
- Audit payload contains organisation name, slug, country code and creator role; it does not store credentials or private onboarding notes.
- Invitation acceptance, role changes, suspension and ownership transfer remain audited.
- Never paste access tokens, credentials, private membership lists or sensitive governance records into general Notion pages.

## Acceptance

- [ ] Authenticated user creates a new organisation and becomes active admin.
- [ ] Duplicate slug displays a recoverable conflict message.
- [ ] Organisation creation and initial membership are atomic and audited.
- [ ] New organisation is selected from the workspace, administration and research routes when passed as `organization_id`.
- [ ] No-organisation empty state links to creation and invitation acceptance.
- [ ] Existing members can create a second organisation without losing their current workspace.
- [ ] Tenant isolation and least-privilege access are tested with two users and two tenants.
- [ ] Browser walkthrough is completed on staging with an authenticated user.
