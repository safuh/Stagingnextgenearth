# Partners, public website and onboarding operations

## One-time setup

Run migrations after deploying the application:

\`\`\`bash
uv run alembic upgrade head
\`\`\`

Create the organisation in the portal with the slug \`nextgen-for-earth\`, then load the public-site starter data:

\`\`\`bash
uv run python scripts/seed_nextgen_demo.py --organization-slug nextgen-for-earth
\`\`\`

The loader is idempotent. It adds missing people, partner, CMS and programme records, including the 12 publication entries currently listed on the public website; it does not create portal accounts or overwrite records that an administrator has already reviewed.

## Founder-facing workspace

Sign in using the founder's portal account, then open:

- \`/workspace/administration\` — membership invitations, roles and governance
- \`/workspace/administration/people\` — people listed on the shared website
- \`/workspace/administration/partners\` — institutional partners, programmes and public catalogue
- \`/workspace/administration/applications\` — volunteer and ambassador applications
- \`/volunteer/apply\` — public volunteer expression-of-interest form

The organisation owner can invite founder and executive roles. Administrators, founders and executives have organisation-administration access. The owner remains the only actor allowed to grant elevated founder, executive or administrator membership.

## Review and publication

### People

Imported website-listed people are created as private and pending. Confirm current role and permission to publish before changing review state and visibility. A directory profile is not a portal login account. Records can be edited, archived or made private at any time.

### Partners

Imported partners begin as private prospects pending verification. Verify the institutional relationship and website details before activating and making a partner public. Partner contacts are not imported by the seed process.

### Programme records

The seed loader creates four programme records in draft state. In the Partners & Public Website workspace:

1. Select **Plan programme**.
2. Select **Open applications** when the programme is ready to accept interest.
3. The public volunteer application page will then list it.

Programme catalogue content and operational programme records are separate: the CMS controls public descriptions, while programme records control operational status and volunteer application availability.

### CMS

CMS records follow this state sequence:

\`draft → review → approved → published\`

A record cannot be published directly from draft or review. The approval actor and timestamp are stored. Published content can be unpublished to draft or archived. Public API responses omit internal source and moderation metadata.

Impact figures imported from the website are source-attributed claims, not independently verified measurements. Preserve that distinction when editing their public descriptions.

## Volunteer and employee onboarding

### Volunteers and ambassadors

1. An applicant creates or signs in to a portal account.
2. They submit an expression of interest for an active programme.
3. A programme manager, administrator, founder or executive reviews the application.
4. Before approval, the reviewer must attest that safeguarding checks and any required parent/guardian consent have been verified.
5. Approval activates the applicant's \`youth_volunteer\` organisation membership.

The application form asks only for programme interest and availability. Applicants should not enter sensitive personal information in the free-text field. The safeguarding checkbox is an operational attestation; it does not collect or replace guardian consent documentation.

### Employees and other staff

An administrator can invite an existing portal account using its registered identifier and assign the employee role. The invitee must accept before the membership becomes active. Do not share accounts or create a staff membership for someone without their consent.

## Data handling

- Keep imported people private until role and publication permission are checked.
- Keep unverified partners private.
- Do not place personal phone numbers, private email addresses, HR files or safeguarding records in public CMS fields.
- Use the public website feed only for approved content and explicitly public partner/person records.
- Archive or make a record private when it is no longer current; do not rely on hiding it in the frontend.
