# Account password and session security

## Self-service password change

An authenticated account can change its password through:

`POST /api/auth/change-password`

Request body:

```json
{
  "current_password": "the-current-password",
  "new_password": "a-new-password-with-at-least-12-characters"
}
```

The API requires a valid access token, verifies the current password against the stored Argon2 hash, requires a replacement password of 12–256 characters, and rejects a replacement identical to the current password. Plaintext passwords are never persisted or logged.

A successful password change:

1. Stores a newly salted Argon2 password hash.
2. Records the password-change timestamp and immediately rejects every older access JWT.
3. Revokes every outstanding refresh-token record for that account, across all devices.
4. Returns the count of refresh sessions revoked.
5. Requires the user to sign in again.

The portal exposes this workflow at `/workspace/security`. It signs the current browser out after the API confirms the change.

## Immediate access-token revocation

A successful password change records `users.password_changed_at` and revokes every outstanding refresh-token record in the same database transaction. Every access JWT carries a server-generated `iat_us` claim (UTC Unix epoch microseconds); the authenticated-request dependency compares that issuance instant with the persisted password-change timestamp. Access JWTs issued before the change are rejected on the next API request, rather than remaining usable until their nominal expiry. Tokens without the required high-resolution issuance claim are rejected after a password change, which safely invalidates legacy sessions. Newly issued access tokens remain valid.

The timestamp comparison uses integer microseconds instead of JWT's standard second-resolution `iat` claim, preventing a token issued in the same second as the password change from slipping through. User records created before this migration have a null change timestamp and retain normal access until the account changes its password.

## Account recovery and administrator support

The self-service endpoint requires the current password. It is not an administrator password-reset endpoint and does not provide email recovery. Before public launch, configure a verified email delivery provider and implement expiring, single-use, hashed recovery tokens with enumeration-resistant responses, rate limits, audit events, and notification after reset. Administrators must not ask users to send passwords through email, chat, or support tickets.

## Operational checks

- Enforce HTTPS and secure HttpOnly session cookies in production.
- Keep access-token lifetimes short and refresh-token rotation enabled.
- Apply distributed rate limits to login and account recovery.
- Alert on repeated failed logins, refresh-token replay, and password changes.
- Require users to update any bootstrap/default password immediately after first sign-in.
- Test password changes against PostgreSQL as well as SQLite before release.
