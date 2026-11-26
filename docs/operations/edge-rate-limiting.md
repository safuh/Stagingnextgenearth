# Edge authentication rate limiting

The FastAPI process limiter is a bounded, per-process backstop. It is not a
shared counter across API workers or replicas. Public deployments should place
a trusted edge in front of the Next.js BFF and enforce shared client-IP limits
there before traffic reaches the application.

The FastAPI API also applies a bounded process-local limit to anonymous
`GET /api/public/organizations/{slug}/climate/*` reads (60 requests per
client/organisation per 60 seconds by default). This protects Render deployments
that expose the API directly, but its counters are not shared across workers or
replicas. Enforce a shared client-IP limit at the managed ingress/WAF when
scaling beyond one API process. The middleware deliberately uses the socket peer
address and does not trust arbitrary forwarded headers.

## Nginx reference configuration

`docker/nginx/nginx.conf` is a standalone Nginx configuration for an edge
container. It forwards to the Compose service name `web:3000` and applies
shared worker-zone limits to the browser-facing credential endpoints:

| Endpoint | Limit | Burst |
| --- | ---: | ---: |
| `POST /api/session/login` | 5/minute/IP | 2 |
| `POST /api/backend/auth/register` | 3/minute/IP | 1 |
| `POST /api/session/logout` | 12/minute/IP | 3 |

Nginx returns HTTP 429 when the configured burst is exceeded. The API's own
refresh endpoint remains protected by the application limiter; refresh is
performed server-to-server by the BFF after an upstream 401 and is not a
browser-facing route. If the API is ever exposed through a separate public
origin, configure an equivalent shared limit on `/api/auth/refresh` at that
API ingress too.

Validate syntax with:

```bash
./scripts/validate_nginx_edge.sh
```

Deploy the edge as the only public HTTP entry point, attach it to the same
private Docker network as `web`, and expose its listener only to the trusted
TLS-terminating ingress. Do not publish the edge's port 8080 directly to the
internet; terminate HTTPS at the managed load balancer or configure TLS in the
edge itself. The sample sets `X-Forwarded-Proto` to `https` because it assumes
that trusted TLS termination occurs immediately upstream.

### Client IP and multiple edge replicas

The sample uses Nginx `$remote_addr` and deliberately does not trust incoming
`X-Forwarded-For`. If a load balancer sits in front, configure Nginx's
`real_ip_header` and `set_real_ip_from` with the exact private CIDRs of that
load balancer only; the load balancer must strip client-supplied forwarding
headers before setting its own. Never trust arbitrary forwarded addresses.

Nginx `limit_req_zone` state is shared among workers in one Nginx instance,
not among independent edge containers. For multiple edge replicas, use an
ingress controller or WAF with a documented cluster-wide/shared-state rate
limiter. Do not claim cluster-wide enforcement from this single-instance
sample. Keep the API process limiter enabled as defense in depth.

## Acceptance checks before public traffic

- Confirm the TLS ingress is the only path to the Nginx listener.
- Confirm spoofed `X-Forwarded-For` cannot change the effective client IP.
- From one test client, exceed each endpoint's configured rate and verify 429.
- From a second client IP, verify its independent bucket remains available.
- Confirm normal login, registration, logout, and BFF session refresh still work.
- Confirm 429s are counted in edge metrics/logs without recording credentials,
  cookies, bearer tokens, or request bodies.
- If running more than one edge replica, verify shared counters at the ingress
  layer rather than relying on this Nginx instance-local configuration.
