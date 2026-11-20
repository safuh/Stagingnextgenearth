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
2. Revokes every outstanding refresh-token record for that account, across all devices.
3. Returns the count of refresh sessions revoked.
4. Requires the user to sign in again.

The portal exposes this workflow at `/workspace/security`. It signs the current browser out after the API confirms the change.

## Access-token expiry boundary

Refresh tokens are revoked immediately. Already-issued access JWTs are stateless and remain valid until their configured short expiry (15 minutes by default). The user interface clears its own session after the change. If immediate revocation of every access token is required by an organisation's threat model, deploy a shared token-version or access-token denylist mechanism before launch; do not represent refresh-token revocation as immediate revocation of all access JWTs.

## Account recovery and administrator support

The self-service endpoint requires the current password. It is not an administrator password-reset endpoint and does not provide email recovery. Before public launch, configure a verified email delivery provider and implement expiring, single-use, hashed recovery tokens with enumeration-resistant responses, rate limits, audit events, and notification after reset. Administrators must not ask users to send passwords through email, chat, or support tickets.

## Operational checks

- Enforce HTTPS and secure HttpOnly session cookies in production.
- Keep access-token lifetimes short and refresh-token rotation enabled.
- Apply distributed rate limits to login and account recovery.
- Alert on repeated failed logins, refresh-token replay, and password changes.
- Require users to update any bootstrap/default password immediately after first sign-in.
- Test password changes against PostgreSQL as well as SQLite before release.
