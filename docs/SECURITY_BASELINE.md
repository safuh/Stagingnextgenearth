# API security baseline

This application applies a conservative HTTP security-header baseline to API
responses:

- `X-Content-Type-Options: nosniff` prevents browser MIME sniffing.
- `X-Frame-Options: DENY` blocks framing of API responses.
- `Referrer-Policy: strict-origin-when-cross-origin` limits referrer disclosure.
- `Permissions-Policy` disables browser capabilities not required by the API.
- `Cross-Origin-Resource-Policy: same-origin` restricts cross-origin resource
  embedding.
- Authentication and session endpoints return `Cache-Control: no-store`
  and `Pragma: no-cache`.
- Production responses add HSTS with `includeSubDomains`. Enable this only
  when every subdomain is HTTPS-capable.

Interactive Swagger, ReDoc and the OpenAPI schema endpoints are disabled when
`ENVIRONMENT=production`. Keep API documentation available only in trusted
non-production environments or publish a separately reviewed, static API
contract.

## Deployment requirements not replaced by middleware

This is a defence-in-depth baseline, not a complete security boundary:

1. Terminate TLS at a trusted ingress/load balancer and configure forwarded
   headers only for known proxy hops.
2. Apply distributed rate limits at the ingress/WAF for login, registration,
   password recovery, invitation acceptance, uploads and expensive research
   endpoints. Do not rely on per-process memory counters in a multi-worker
   deployment.
3. Configure request-body and upload limits at both ingress and application
   layers.
4. Use managed secrets, rotate signing credentials, and keep production
   credentials out of source control and logs.
5. Add monitoring for authentication failures, invitation abuse, authorization
   denials, file scanning failures and unusual export volume.
6. Complete independent penetration testing, privacy review, backup/restore
   exercises and incident-response rehearsal before public launch.

The middleware does not implement CSP because the API and interactive API
documentation have different content requirements. The public Next.js frontend
must define and test its own Content Security Policy and browser security
headers at the web tier.
