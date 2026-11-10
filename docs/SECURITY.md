# Security & Deployment Guidance

Stagingnextgenearth provides authentication primitives and an application lifecycle, but it does not make deployment security automatic. Consuming applications remain responsible for infrastructure, secret management, abuse controls, and authorization policy.

## Threat model

The authentication boundary is designed to reduce the following risks:

| Threat | Backbone control | Deployment responsibility |
| --- | --- | --- |
| Password disclosure | Passwords are hashed before persistence; authentication failures are generic | Use a modern password-hashing configuration and protect database access/backups |
| JWT tampering | Tokens are signed and validated with the configured algorithm and secret | Keep the signing secret out of source control and rotate it through a controlled deployment process |
| Access/refresh token confusion | Token type is validated at the refresh boundary | Keep token lifetimes appropriate for the application's risk profile |
| Refresh-token replay | Refresh tokens are consumed during rotation and can be explicitly revoked | Protect refresh tokens in clients and revoke sessions when required |
| User enumeration | Login failures use a generic invalid-credentials response; duplicate registration has a distinct conflict response | Consider product-specific privacy requirements before exposing account-existence workflows |
| Credential/token leakage | Authentication errors do not intentionally echo credentials or tokens | Do not log passwords, authorization headers, refresh tokens, or raw JWTs |
| Transport interception | No transport security is assumed by the library | Terminate TLS and use HTTPS for every authenticated request |
| Brute-force abuse | Rate limiting is intentionally outside the current authentication contract | Apply rate limiting, lockout/backoff, bot controls, and monitoring at the appropriate edge |

This is a focused application threat model, not a complete infrastructure threat model. Review it again when adding OAuth providers, RBAC/scopes, rate limiting, browser sessions, or other authentication mechanisms.

## Production deployment requirements

### Signing secrets

- Provide the JWT signing secret through a dedicated secret-management mechanism or protected runtime environment.
- The configured secret must meet the backbone's minimum length requirement of 32 characters; use high-entropy randomly generated material rather than a human password.
- Never commit secrets to the repository, images, test fixtures used by production, or logs.
- Plan key rotation before production launch. Rotation normally requires a controlled overlap or token invalidation strategy because existing JWTs are signed with the previous key.
- Treat a leaked signing key as a security incident: revoke affected refresh sessions, rotate the key, and assess issued access tokens.

### Passwords and credentials

- Persist only password hashes, never plaintext passwords.
- Use the application's password-hashing library and review its cost parameters as hardware changes.
- Protect the identity database, backups, exports, and administrative access as credential-bearing systems.
- If a login result indicates that a password needs rehashing, upgrade the stored hash through the consuming application's credential-management workflow.

### Tokens and sessions

- Use short-lived access tokens for APIs and longer-lived refresh tokens only where session continuity is required.
- Store refresh tokens in a client mechanism appropriate to the client platform and threat model; avoid exposing them to unnecessary application code or logs.
- Preserve refresh-token rotation and revocation semantics. A previously consumed refresh token must not be accepted again.
- Revoke refresh sessions on logout and when compromise is suspected.
- Do not put secrets, passwords, or unnecessary personal data into JWT claims. JWT payloads are signed, not encrypted.

### Transport and browser security

- Require HTTPS in production, including between reverse proxies and application services when the network path is not otherwise trusted.
- Configure CORS to explicit trusted origins. Do not use a permissive wildcard policy for authenticated browser applications without a deliberate security review.
- Apply secure cookie attributes when cookies are used by the consuming application (`Secure`, appropriate `HttpOnly`, and an intentional `SameSite` policy).
- Configure trusted proxy/header handling narrowly so clients cannot forge security-relevant forwarded metadata.

### Database and migrations

- Keep database credentials in protected runtime configuration.
- Restrict database network access to the services that require it.
- Run Alembic migrations as an explicit release operation rather than automatically from every API process.
- Test migration upgrade/downgrade behavior before production rollout and retain a rollback/recovery procedure.

### Logging and observability

- Correlation IDs are useful for tracing authentication failures without exposing credentials.
- Structured logs should record operational context, not passwords, raw authorization headers, refresh tokens, or complete JWTs.
- Review exception handling and access logs at the deployment boundary for accidental credential disclosure.
- Feed authentication failures, refresh-token replay/revocation events, and infrastructure alerts into the application's monitoring strategy as appropriate.

## Controls intentionally outside this milestone

The backbone currently does not provide a complete abuse-prevention or authorization policy. These remain explicit follow-up controls:

- RBAC and OAuth2 scopes.
- Rate limiting and abuse controls.
- OpenTelemetry and metrics.
- Structured identity audit events.
- Secret scanning and SBOM/release provenance.

These controls should be implemented and verified before making stronger production-security claims for applications that require them.

## Security reporting

Do not disclose suspected vulnerabilities in public issue threads before maintainers have had an opportunity to assess them. Use the repository's configured private security-reporting mechanism when one is available; otherwise contact the project maintainer privately with reproduction details and affected versions.
