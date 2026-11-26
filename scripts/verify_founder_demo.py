#!/usr/bin/env python3
"""Read-only API/web preflight for a founder demo or staging environment.

Required environment: FOUNDER_IDENTIFIER, FOUNDER_PASSWORD, ORGANIZATION_SLUG.
Optional environment: API_BASE_URL (defaults to local API), WEB_BASE_URL.
The script never prints credentials or token material and never mutates data.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


class PreflightError(RuntimeError):
    """A founder-demo acceptance check failed."""


class ApiClient:
    def __init__(
        self,
        base_url: str,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = opener
        self.token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=payload, headers=headers, method=method
        )
        try:
            with self.opener(request, timeout=15) as response:
                raw = response.read()
                if response.status < 200 or response.status >= 300:
                    raise PreflightError(f"{method} {path}: unexpected HTTP {response.status}")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raise PreflightError(f"{method} {path}: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise PreflightError(f"{method} {path}: connection failed ({exc.reason})") from exc
        except json.JSONDecodeError as exc:
            raise PreflightError(f"{method} {path}: response was not valid JSON") from exc


def _check_public_payload(items: Any, allowed_fields: set[str], label: str) -> int:
    if not isinstance(items, list):
        raise PreflightError(f"Public {label} endpoint did not return a list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise PreflightError(f"Public {label} item {index} is not an object")
        unexpected = set(item) - allowed_fields
        if unexpected:
            raise PreflightError(
                f"Public {label} item {index} exposes unexpected fields: "
                f"{', '.join(sorted(unexpected))}"
            )
    return len(items)


def verify_founder_demo(
    *,
    api_base_url: str,
    identifier: str,
    password: str,
    organization_slug: str,
    web_base_url: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[str]:
    """Verify readiness, owner identity, public feeds and optional web reachability."""
    client = ApiClient(api_base_url, opener)
    checks: list[str] = []

    health = client.request("GET", "/health/ready")
    if not isinstance(health, dict) or health.get("status") != "ready":
        raise PreflightError("API readiness endpoint did not report ready")
    checks.append("API readiness and database connectivity")

    login = client.request(
        "POST", "/auth/login", {"identifier": identifier, "password": password}
    )
    if not isinstance(login, dict) or not isinstance(login.get("access_token"), str):
        raise PreflightError("Founder login did not return an access token")
    client.token = login["access_token"]
    checks.append("Founder credentials accepted")

    context = client.request("GET", "/auth/context")
    if not isinstance(context, dict) or not isinstance(context.get("user_id"), str):
        raise PreflightError("Authentication context is incomplete")
    user_id = context["user_id"]
    if str(context.get("identifier", "")).casefold() != identifier.casefold():
        raise PreflightError("Authenticated identity does not match the supplied founder account")
    matching = [
        item for item in context.get("memberships", [])
        if isinstance(item, dict) and item.get("organization_slug") == organization_slug
    ]
    if len(matching) != 1:
        raise PreflightError(
            f"Expected exactly one membership for organisation {organization_slug!r}"
        )
    membership = matching[0]
    raw_roles = membership.get("roles", [])
    roles = set(raw_roles) if isinstance(raw_roles, list) else set()
    if membership.get("status") != "active" or "admin" not in roles:
        raise PreflightError("Founder account must have an active administrator membership")
    checks.append("Active organisation administrator membership")

    organizations = client.request("GET", "/organizations")
    organization = next(
        (
            item
            for item in organizations
            if isinstance(item, dict) and item.get("slug") == organization_slug
        ),
        None,
    ) if isinstance(organizations, list) else None
    if not isinstance(organization, dict) or not isinstance(organization.get("id"), str):
        raise PreflightError("Founder account cannot resolve its active organisation")
    organization_id = organization["id"]

    summary = client.request(
        "GET", f"/organizations/{organization_id}/administration-summary"
    )
    if not isinstance(summary, dict) or summary.get("owner_user_id") != user_id:
        raise PreflightError("Signed-in founder is not the recorded organisation owner")
    checks.append("Founder identity matches recorded organisation owner")

    members = client.request("GET", f"/organizations/{organization_id}/memberships")
    owner_membership = next(
        (item for item in members if isinstance(item, dict) and item.get("user_id") == user_id),
        None,
    ) if isinstance(members, list) else None
    if not isinstance(owner_membership, dict) or owner_membership.get("status") != "active":
        raise PreflightError("Organisation owner membership is not active")
    checks.append("Organisation membership administration endpoint")

    content_count = _check_public_payload(
        client.request("GET", f"/public/organizations/{organization_slug}/content"),
        {"id", "content_type", "slug", "title", "summary", "body", "published_at"},
        "CMS content",
    )
    programme_count = _check_public_payload(
        client.request("GET", f"/public/organizations/{organization_slug}/programmes"),
        {"id", "organization_id", "title", "slug", "summary", "status", "start_date", "end_date"},
        "programmes",
    )
    checks.append(
        f"Public feed schemas safe ({content_count} published CMS items, "
        f"{programme_count} visible programmes)"
    )

    if web_base_url:
        request = urllib.request.Request(
            web_base_url.rstrip("/") + "/",
            headers={"Accept": "text/html"},
            method="GET",
        )
        try:
            with opener(request, timeout=15) as response:
                if response.status < 200 or response.status >= 300:
                    raise PreflightError(f"Web homepage returned HTTP {response.status}")
                if b"NextGen" not in response.read(2_000_000):
                    raise PreflightError("Web homepage did not contain the expected site marker")
        except urllib.error.HTTPError as exc:
            raise PreflightError(f"Web homepage: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise PreflightError(f"Web homepage: connection failed ({exc.reason})") from exc
        checks.append("Public web homepage reachable")

    return checks


def main() -> int:
    required = ("FOUNDER_IDENTIFIER", "FOUNDER_PASSWORD", "ORGANIZATION_SLUG")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        checks = verify_founder_demo(
            api_base_url=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api"),
            identifier=os.environ["FOUNDER_IDENTIFIER"],
            password=os.environ["FOUNDER_PASSWORD"],
            organization_slug=os.environ["ORGANIZATION_SLUG"],
            web_base_url=os.environ.get("WEB_BASE_URL") or None,
        )
    except PreflightError as exc:
        print(f"Founder demo preflight FAILED: {exc}", file=sys.stderr)
        return 1
    for check in checks:
        print(f"PASS  {check}")
    print(f"Founder demo preflight passed ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
