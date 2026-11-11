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


## Programme participation applications

Active members with the `youth_volunteer` role can submit volunteer or ambassador applications to additional programmes from the youth workspace. Existing non-volunteer or inactive memberships cannot use this path. Applications are unique per organisation, programme and account; managers review them through the programme application queue. Approving an existing active youth volunteer does not create a duplicate membership. New applicants without an organisation membership are still enrolled as youth volunteers when approved.

The youth portal collects only participation type, a short statement of interest and optional availability. It does not request personal contact details, precise location, school details or sensitive information. Application status and manager review notes are returned only to the applicant through the caller-scoped history endpoint.
