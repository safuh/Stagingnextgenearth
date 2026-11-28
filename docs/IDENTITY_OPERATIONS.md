# Identity, invitations and account security operations

**Milestone:** M173 — identity lifecycle and secure onboarding  
**Implementation branch:** `feat/identity-lifecycle-m173`  
**Status:** implementation, full local backend suite (326 passed, 4 skipped), focused frontend checks and disposable PostgreSQL/PostGIS migration upgrade/downgrade/re-upgrade acceptance passed; production mail/OIDC credentials and live acceptance remain deployment prerequisites.

## Operating model

NextGen for Earth uses one local account identity across learner, staff, researcher, volunteer, institutional partner and funder experiences. Organisation membership roles determine tenant access. Google sign-in authenticates an existing local account; it does not create an organisation membership or grant a role.

Production public registration remains disabled. New accounts enter through an organisation-scoped invitation. A successful invitation proves control of the invited mailbox, creates or reuses the account, verifies the email address and activates only the roles recorded in the invitation. Administrator, founder and executive role grants are owner-only; the `funder` role is distinct and does not inherit administrator privileges.

## Security properties

- Invitation, password-reset, email-verification, email-change and Google OIDC state tokens are generated with cryptographically secure randomness. Only SHA-256 token digests are stored for one-time action tokens.
- Tokens have explicit expiry, consumed and revoked timestamps. Resending rotates the token and invalidates the previous token.
- Invitation links place the token in the URL fragment (`#token=`); fragments are not sent in HTTP requests or referrer headers. The frontend removes the fragment before submitting the token in a POST body.
- Existing accounts must prove knowledge of their current password when accepting an invitation. Invitations for an email already attached to a different account ID are rejected.
- Email-change requests require the current password. The old address remains active until the new mailbox is confirmed. Confirmation revokes refresh sessions and invalidates previously issued access tokens.
- Password recovery responses do not reveal whether an account exists. Successful recovery revokes refresh sessions and invalidates old access tokens.
- Google OIDC uses authorization code, a browser-bound HttpOnly state cookie plus server-side one-time state, nonce, PKCE S256, Google JWKS signature validation, issuer/audience/expiry validation and `email_verified=true`. Provider subjects are stored as stable external identities. A verified email may be linked to an existing matching local account; an unverified email claim is never used to link accounts. Google cannot create an uninvited account or grant tenant roles.
- Learner course invitations are tenant-checked against a published course and may include a matching open cohort. Acceptance creates an approved course enrolment. Programme/course scopes currently apply to learner-only invitations; programme-scoped staff/researcher permissions require a later policy-enforcement milestone and are deliberately rejected rather than represented as enforced when they are not.
- `funder` is a distinct organisation role. The funder portal and funding-record permissions remain M174 scope; the role itself does not grant administrator or partner-report access.
- SMTP credentials and Google OAuth secrets are deployment-only settings. Never commit them to source control, Notion, issue bodies, audit records or logs.

## Database changes

- `0070_identity_lifecycle`: adds `users.email_verified_at`, `identity_action_tokens` and `external_identities`.
- `0071_funder_membership_role`: adds `funder` to the organisation membership and role-assignment constraints.

Deployments must apply Alembic migrations before the API serves requests. The identity action-token table is intentionally shared by invitation, recovery, email-change, verification and short-lived Google state workflows; the `purpose` check constraint limits its use.

## SMTP configuration

Configure the following on the API Render service only after verifying the sending domain and sender identity:

| Setting | Purpose |
|---|---|
| `SMTP_HOST` | Provider SMTP hostname |
| `SMTP_PORT` | SMTP port; defaults to 587 |
| `SMTP_USERNAME` | Optional provider username |
| `SMTP_PASSWORD` | Provider credential (secret) |
| `SMTP_SENDER` | Verified From address |
| `SMTP_STARTTLS` | Defaults to true |
| `SMTP_TIMEOUT_SECONDS` | Bounded delivery timeout |

If SMTP is not configured, production invitation creation records the invitation but returns `503 invitation_delivery_unavailable`; administrators can configure SMTP and rotate/resend from Organisation Administration. Password-reset requests remain non-enumerating and do not disclose delivery state to the requester. Do not treat a recorded invitation as delivered.

## Google OAuth configuration

Configure an OAuth 2.0 Web application in Google Cloud and add this exact authorised redirect URI:

`https://nextgen-web-upag.onrender.com/api/session/google/callback`

Set the following on the API Render service:

- `GOOGLE_OIDC_CLIENT_ID`
- `GOOGLE_OIDC_CLIENT_SECRET` (secret)
- `GOOGLE_OIDC_REDIRECT_URI` (the exact callback URI above)

The web BFF owns the browser callback and HttpOnly session cookies. The API owns OIDC state/nonce/PKCE verification, token exchange, Google ID-token validation and local identity linking. The OAuth callback cookie uses `SameSite=Lax` for the top-level return from Google; ordinary authenticated mutations continue to use the same-origin/CSRF controls.

## User-facing journeys

- Staff: `/staff/login` → email/password or Google → organisation workspace.
- Learners: `/learners/sign-in` → email/password or Google → learner portal.
- New invitee: emailed link → `/onboarding/accept` → create password (or prove existing account password) → assigned membership activation.
- Password recovery: `/account/recover` → request email → set new password.
- Email verification: authenticated account security page → request verification → `/account/verify`.
- Email change: `/account/security` → confirm current password and new address → `/account/confirm-email-change`.
- Account controls: `/account/security` → password change, Google sign-in connection, email verification/change and global session revocation.
- Organisation administrators: `/workspace/administration` → invite new person, inspect invitations, rotate/resend or revoke; existing-account membership invitations remain available separately.

## API surface

- `POST /api/organizations/{organization_id}/onboarding-invitations`
- `GET /api/organizations/{organization_id}/onboarding-invitations`
- `POST /api/organizations/{organization_id}/onboarding-invitations/{invitation_id}/resend`
- `DELETE /api/organizations/{organization_id}/onboarding-invitations/{invitation_id}`
- `POST /api/auth/invitations/accept`
- `POST /api/auth/password-reset/request` and `/confirm`
- `POST /api/auth/email-verification/request` and `/confirm`
- `POST /api/auth/email-change/request` and `/confirm`
- `GET /api/auth/google/start` and `/callback`
- `GET /api/auth/connections`
- `POST /api/auth/sessions/revoke-all`

Credential endpoints and Google authorization start/callback are subject to the process-local authentication rate limiter. Production must also enforce distributed limits at the trusted ingress/API gateway; the in-process limiter is not a multi-replica substitute.

## Release and acceptance checklist

1. Apply migrations `0070` and `0071` to staging PostgreSQL.
2. Configure and verify SMTP sender/domain; send an invitation to a controlled mailbox.
3. Configure Google OAuth client and exact redirect URI; verify Google sign-in for an already invited account.
4. Create a learner invitation scoped to a published course and verify approved enrolment after acceptance.
5. Verify multi-role staff and funder invitations do not gain administrator permissions.
6. Verify expired, replayed, rotated and revoked tokens fail; verify existing-account invitation requires the current password.
7. Verify password reset, email change and global session revocation invalidate prior refresh/access sessions.
8. Verify cross-tenant invitations, course IDs and cohort IDs are rejected.
9. Verify account security, learner sign-in and staff sign-in in a real browser on the exact deployed SHA.
10. Confirm delivery failures, provider errors and invitation lifecycle events are observable without logging raw tokens or passwords.

## Known deployment dependencies and remaining scope

- SMTP and Google OAuth credentials have been declared as Render configuration inputs but have not been supplied or validated in this environment. Production invitation delivery and Google sign-in therefore remain disabled until configured.
- The hosted Render database blocks the hosted query service through its IP allowlist. Do not widen the allowlist merely for verification; use the authorised local database tunnel/connection path or an application-level read-only verification.
- The migration integration test passed against a disposable PostgreSQL 17/PostGIS 3.5 database. Production migration acceptance remains a separate release gate.
- Programme/course scopes for staff, researchers and partners need end-to-end policy enforcement across their APIs before they can be offered as restricted staff invitations.
- M174 completes partner/funder lifecycle, agreements, deliverables and reporting. M175 completes research and climate intelligence integration and evidence-backed reporting.
