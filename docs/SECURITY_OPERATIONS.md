# Security operations baseline

For self-service password changes, refresh-session revocation, and account-recovery launch requirements, see [Account security operations](operations/account-security.md). For the deployable Nginx edge reference and shared ingress requirements, see [Edge authentication rate limiting](operations/edge-rate-limiting.md).

## Authentication request limits

The API applies a fixed-window, per-client-IP request limit to password login,
registration, refresh, and logout endpoints. Defaults are 30 requests per
endpoint per 60 seconds. Responses include `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, and, when blocked, `Retry-After`; blocked requests
receive HTTP 429 with a generic error message. Configure `AUTH_RATE_LIMIT_REQUESTS`
and `AUTH_RATE_LIMIT_WINDOW_SECONDS` through the environment; defaults are 30 and
60 respectively.

The limiter intentionally uses the socket peer address and does not trust
client-supplied `X-Forwarded-For` or `Forwarded` headers. Configure the reverse
proxy to strip incoming forwarding headers and set trusted proxy metadata at
the ingress layer. Do not enable trust in arbitrary client-provided addresses.

The in-process limiter is bounded to 20,000 tracked client/endpoint buckets and
is a defense-in-depth control for a single worker. Its counters are not shared
between workers, containers, or replicas and reset when a process restarts.
Production deployments must enforce the same or stricter limits at the trusted
load balancer, ingress controller, or API gateway with shared state. Monitor
HTTP 429 rates and authentication failures without logging credentials, tokens,
or raw password values.

## Operational requirements before public launch

- Terminate TLS at a trusted ingress and enable HSTS only when HTTPS is enforced.
- Configure explicit CORS origins; do not combine wildcard origins with cookies.
- Keep JWT and object-storage secrets in a managed secret store and rotate them.
- Use PostgreSQL backups with tested restore procedures and point-in-time recovery.
- Centralize logs and metrics; alert on repeated authentication failures, 429s,
  refresh-token replay, elevated 5xx responses, and storage/scanner outages.
- Apply distributed edge rate limits before exposing multiple application workers.
