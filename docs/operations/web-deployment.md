# Web application deployment

The Next.js application uses a same-origin backend-for-frontend (BFF). Browser
code calls `/api/backend/*`; the BFF forwards requests to FastAPI and keeps
access and refresh tokens in HttpOnly cookies. Browser JavaScript never receives
either token.

## Required configuration

Set these variables in the Next.js server environment:

- `BACKEND_API_URL`: FastAPI API base URL, including the API prefix, for
  example `https://api.example.org/api`. This URL must be reachable from the
  Next.js server, not necessarily from the user's browser.
- `ACCESS_TOKEN_MINUTES`: must match FastAPI's access-token lifetime (default
  `15`).
- `REFRESH_TOKEN_DAYS`: must match FastAPI's refresh-token lifetime (default
  `14`).

The example values are in `web/.env.example`. Do not use a
`NEXT_PUBLIC_*` variable for backend credentials or internal service URLs.
The BFF retains a localhost fallback for local development only.

## Session and request security

- Sign-in exchanges credentials server-to-server with FastAPI.
- Access and rotating refresh tokens are set as `HttpOnly`, `SameSite=Strict`,
  path-root cookies; the `Secure` flag is enabled in production.
- The browser sends same-origin requests to the BFF. The BFF adds the bearer
  access token and retries one 401 response after rotating the refresh token.
- Mutating BFF and session requests reject a supplied cross-origin Origin header.
  Keep the application on HTTPS in production.
- Sign-out revokes the refresh token where possible and clears both cookies.
- Session restoration rotates the refresh token and returns only the account
  subject and authenticated state.
- The BFF streams upstream response bodies and does not cache API responses.

The BFF is not a replacement for API authorization. FastAPI must continue to
validate the account, organisation membership, role, resource ownership and
tenant boundary on every protected operation.

## Deployment topology

Place the browser-facing Next.js application behind HTTPS. Keep FastAPI and
PostgreSQL on private service networks where practical. Configure the BFF's
`BACKEND_API_URL` to the internal API service address when both services share
a private network. Apply database migrations as a separate deployment step;
do not run migrations in Next.js or API worker startup.

## Operational checks

1. Verify that login responses contain only the account subject, not tokens.
2. Verify that browser storage and JavaScript cannot read `nfe_access` or
   `nfe_refresh`.
3. Verify that a page reload restores a valid session.
4. Verify that expired access tokens are refreshed once and that expired or
   revoked refresh tokens clear the browser session.
5. Verify that cross-origin mutation requests are rejected.
6. Verify that sign-out invalidates the refresh token and clears both cookies.
7. Verify that the Next.js server can reach FastAPI and that the browser does
   not need direct API-origin access for authenticated workflows.
