# Security Policy

Stagingnextgenearth is infrastructure. Security issues can affect every application generated from or built on it, so security reports are handled with priority.

## Reporting

Please do not publish credentials, exploit details, or sensitive vulnerability information in public GitHub issues. Use GitHub's private security reporting mechanism for this repository when available.

Include:

- affected version/commit;
- affected component;
- security impact;
- reproduction steps or a minimal proof of concept; and
- any suggested mitigation.

## Security principles

- Secrets are supplied through runtime configuration, not source control.
- JWT signing keys must be high-entropy and protected by the deployment environment.
- Access tokens should be short-lived.
- Refresh-token rotation/revocation is required before the identity module is considered production-ready.
- Dependencies must be scanned in CI.
- Generated Docker images must not contain development secrets.
- Kubernetes manifests must contain placeholders, never real credentials.

## Supported versions

Before v1.0, security fixes target the current development line. Once v1.0 is released, the project will publish an explicit support window.
