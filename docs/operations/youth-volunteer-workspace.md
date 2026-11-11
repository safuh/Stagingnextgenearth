# Youth and volunteer workspace

The Next.js route `/workspace/youth` is available to active
`youth_volunteer` members. It provides a personal view of:

- Published learning courses and each caller's own course progress.
- Volunteer application history within the active organisation.
- Activity assignments made to the caller.
- The caller's mentorship and attendance records.
- Organisation programme summaries.

## API contracts

The dashboard reads the caller's membership from
`GET /organizations/{organization_id}/memberships/me`. It then loads
published courses, programme summaries, and the existing personal learning
history endpoints.

Two caller-scoped programme endpoints support the personal history panels:

- `GET /organizations/{organization_id}/my-volunteer-applications`
- `GET /organizations/{organization_id}/my-volunteer-allocations`

Both derive the user identity from the authenticated principal. The client
cannot supply a user ID to retrieve another person's records. Responses are
tenant-scoped and bounded (100 applications and 200 allocations). The
allocation response contains activity and programme details, not other
volunteers' identities.

## Privacy and safeguarding

The page does not provide a public member directory, expose other applicants'
interest statements, or display child-level programme participation data.
Staff assignment and application review remain server-authorised workflows.
The UI role check is for navigation only; API authorization remains
independent.

This initial portal is read-only for programme applications and assignments.
It does not add direct messaging, public profiles, location tracking, or
unmoderated contact between participants. Any future learner communication
or enrolment features involving minors require appropriate safeguarding,
consent and access controls before implementation.

## Remaining work

Dedicated application submission and withdrawal UX, staff feedback workflows,
accessible course learning interactions, certificate presentation and richer
programme participation views are not included in this increment.
