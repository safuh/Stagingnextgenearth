# Identity, sign-in and onboarding

## One identity system, separate user journeys

The platform uses one account identity and authentication service. The browser-facing entry points are intentionally different because public learners, staff and institutional partners have different onboarding and authorization requirements.

| Audience | Entry point | Account creation | How organisation access is granted |
| --- | --- | --- | --- |
| Learners | `/learners` | Self-registration | Apply to a published course. A course manager reviews the application. Approval creates an active `learner` membership. |
| Volunteers | `/volunteer/apply` | Register through `/learners`, then return to the application | Programme team reviews the volunteer application and completes safeguarding checks before granting `youth_volunteer` membership. |
| Employees, researchers and programme staff | `/staff/register` | Self-register an identity, or use an existing account | An administrator invites the exact registered email and assigns a permitted role. The invitee signs in and accepts the invitation. |
| Founder / executive / administrator | `/staff/register` for initial identity only | Self-register an identity | Organisation owner grants privileged roles; they cannot be selected during public registration. |
| Institutional partners | `/staff/register` | Partner contact registers an identity | Organisation administrator invites the account as `institutional_partner`; invitation acceptance activates membership. |

A registered identity is not an organisation membership. A user cannot select or grant themselves staff, founder, executive, administrator, researcher or partner permissions during registration.

## Authentication endpoints

The same backend authentication API serves all journeys:

- `POST /api/auth/register` creates an identity and password hash. It does not create an organisation membership.
- `POST /api/auth/login` authenticates the identity and issues access and refresh tokens.
- The Next.js same-origin session endpoint `POST /api/session/login` stores tokens in HttpOnly, Secure-in-production, SameSite=Strict cookies.
- `GET /api/session` reports whether the browser has a session.
- Protected API requests pass through the same-origin backend proxy; refresh-token rotation occurs after an upstream 401.
- `POST /api/auth/refresh` rotates refresh credentials through the backend lifecycle.
- `POST /api/auth/logout` revokes the refresh token.

## Learner lifecycle

1. Learner creates an account at `/learners`; the UI registers and signs in using the shared authentication service.
2. The portal reads published courses from `GET /api/public/organizations/{slug}/courses`.
3. The learner submits an application using authenticated `POST /api/organizations/{organization_id}/learning/courses/{course_id}/enrollments`. A pre-existing staff/partner or suspended membership cannot be used to bypass role controls.
4. The learner sees their own application status from `GET /api/organizations/{organization_id}/learning/my-enrollments`.
5. An authorised programme manager reviews the application at `POST /api/organizations/{organization_id}/learning/courses/{course_id}/enrollments/{learner_id}/decision`.
6. Approval creates an active `learner` membership when the applicant does not already have an eligible learning membership. The learner can then use the protected curriculum, lesson, assessment, progress and certificate workflows.

A pending application does not grant course content access. Rejection does not create a membership.

## Staff and partner lifecycle

1. User registers an identity at `/staff/register` (or signs in to an existing account).
2. User gives the administrator the exact registered email address.
3. An active administrator creates an invitation using `POST /api/organizations/{organization_id}/memberships`.
4. The administrator shares the generated private invitation URL with the intended recipient.
5. Recipient signs in and accepts using `POST /api/organizations/{organization_id}/memberships/{membership_id}/accept`.
6. The API verifies the authenticated subject matches the invited user. Only then is the membership activated.

The invitation link is not a bearer credential: it cannot be accepted by another signed-in account. Privileged roles remain owner-controlled.

## Security and operational notes

- The learner role is a tenant-scoped membership role, not an authentication identity type.
- The same account can participate in more than one organisation, subject to each organisation's own membership records.
- Public directory records are not login accounts.
- No initial passwords are embedded in seed data or presentation material.
- Never share passwords or invitation links publicly.
- CMS publication remains a separate editorial permission: authors cannot approve their own content.
- Youth/volunteer participation remains subject to the programme's safeguarding and any required parent/guardian consent checks.

## Local verification

After pulling the branch:

```bash
uv run alembic upgrade head
uv run pytest tests/test_learning.py -q
uv run ruff check .
cd web && npm ci && npm run lint && npm run build
```

Run the full backend suite and PostGIS migration integration suite before production deployment. Do not reset or delete existing database volumes to apply migrations.
