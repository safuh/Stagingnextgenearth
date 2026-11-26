"""Tests for the read-only founder demo preflight."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from scripts.verify_founder_demo import PreflightError, verify_founder_demo


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        raw = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return raw if limit < 0 else raw[:limit]


def fake_opener(responses: dict[str, Any]) -> Callable[..., FakeResponse]:
    def open_request(request: Any, timeout: int = 15) -> FakeResponse:
        path = request.full_url.split("/api", 1)[-1] if "/api" in request.full_url else "/"
        if path not in responses:
            raise AssertionError(f"Unexpected request: {request.method} {path}")
        payload = responses[path]
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(payload)
    return open_request


def responses(*, roles: list[str] | None = None, owner_id: str = "user-1") -> dict[str, Any]:
    return {
        "/health/ready": {"status": "ready"},
        "/auth/login": {"access_token": "secret-token"},
        "/auth/context": {
            "user_id": "user-1", "identifier": "founder@example.test",
            "memberships": [{
                "organization_slug": "demo-org", "status": "active",
                "roles": roles if roles is not None else ["admin"],
            }],
        },
        "/organizations": [{"id": "org-1", "slug": "demo-org"}],
        "/organizations/org-1/administration-summary": {"owner_user_id": owner_id},
        "/organizations/org-1/memberships": [{"user_id": "user-1", "status": "active"}],
        "/public/organizations/demo-org/content": [],
        "/public/organizations/demo-org/programmes": [],
    }


def test_founder_preflight_checks_owner_and_public_feeds() -> None:
    checks = verify_founder_demo(
        api_base_url="https://example.test/api", identifier="founder@example.test",
        password="not-printed", organization_slug="demo-org",
        opener=fake_opener(responses()),
    )
    assert len(checks) == 6
    assert any("recorded organisation owner" in item for item in checks)


def test_founder_preflight_rejects_non_owner_admin() -> None:
    data = responses(owner_id="someone-else")
    with pytest.raises(PreflightError, match="not the recorded organisation owner"):
        verify_founder_demo(
            api_base_url="https://example.test/api", identifier="founder@example.test",
            password="not-printed", organization_slug="demo-org", opener=fake_opener(data),
        )


def test_founder_preflight_rejects_learner_only_membership() -> None:
    with pytest.raises(PreflightError, match="active administrator membership"):
        verify_founder_demo(
            api_base_url="https://example.test/api", identifier="founder@example.test",
            password="not-printed", organization_slug="demo-org",
            opener=fake_opener(responses(roles=["learner"])),
        )


def test_founder_preflight_checks_optional_web_homepage() -> None:
    data = responses()
    data["/"] = b"<html>NextGen For Earth</html>"
    checks = verify_founder_demo(
        api_base_url="https://example.test/api", identifier="founder@example.test",
        password="not-printed", organization_slug="demo-org",
        web_base_url="https://example.test", opener=fake_opener(data),
    )
    assert "Public web homepage reachable" in checks


def test_founder_preflight_rejects_identity_mismatch() -> None:
    data = responses()
    data["/auth/context"]["identifier"] = "another@example.test"
    with pytest.raises(PreflightError, match="does not match the supplied founder account"):
        verify_founder_demo(
            api_base_url="https://example.test/api", identifier="founder@example.test",
            password="not-printed", organization_slug="demo-org", opener=fake_opener(data),
        )


def test_founder_preflight_rejects_private_fields_in_public_content() -> None:
    data = responses()
    data["/public/organizations/demo-org/content"] = [{
        "id": "content-1", "title": "Public", "source_url": "private-metadata",
    }]
    with pytest.raises(PreflightError, match="unexpected fields: source_url"):
        verify_founder_demo(
            api_base_url="https://example.test/api", identifier="founder@example.test",
            password="not-printed", organization_slug="demo-org", opener=fake_opener(data),
        )


def test_founder_preflight_rejects_private_fields_in_public_programmes() -> None:
    data = responses()
    data["/public/organizations/demo-org/programmes"] = [{
        "id": "programme-1", "title": "Public", "created_by": "private-user",
    }]
    with pytest.raises(PreflightError, match="unexpected fields: created_by"):
        verify_founder_demo(
            api_base_url="https://example.test/api", identifier="founder@example.test",
            password="not-printed", organization_slug="demo-org", opener=fake_opener(data),
        )
