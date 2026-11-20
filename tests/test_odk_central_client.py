"""Protocol-level ODK Central client tests using HTTPX MockTransport only."""

import asyncio
from collections.abc import Callable

import httpx
import pytest

from stagingnextgenearth.workers.odk_sync import ODKCentralClient


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> ODKCentralClient:
    client = ODKCentralClient("https://central.example.org", "sync@example.org", "secret")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def test_session_auth_forms_and_revocation_use_expected_protocol() -> None:
    seen: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.method == "POST":
            assert request.read() == b'{"email":"sync@example.org","password":"secret"}'
            return httpx.Response(200, json={"token": "token/with-special+chars"})
        if request.method == "GET":
            assert request.headers.get("Authorization") == "Bearer token/with-special+chars"
            return httpx.Response(200, json=[{"xmlFormId": "rainfall-v1"}])
        return httpx.Response(204)

    async def exercise() -> list[dict[str, object]]:
        central = _client(handler)
        async with central:
            forms = await central.list_forms(17)
        return forms

    forms = asyncio.run(exercise())
    assert forms == [{"xmlFormId": "rainfall-v1"}]
    assert seen == [
        ("POST", "/v1/sessions", None),
        ("GET", "/v1/projects/17/forms", "Bearer token/with-special+chars"),
        ("DELETE", "/v1/sessions/token%2Fwith-special%2Bchars", None),
    ]


def test_odata_pagination_follows_same_origin_next_link(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"token": "test-token"})
        if request.url.path.endswith("/Submissions") and request.url.params.get("$top") == "100":
            return httpx.Response(
                200,
                json={
                    "value": [{"__id": "one"}],
                    "@odata.nextLink": (
                        "https://central.example.org/v1/projects/17/forms/rainfall.svc/"
                        "Submissions?$skiptoken=page-2"
                    ),
                },
            )
        if request.url.params.get("$skiptoken") == "page-2":
            return httpx.Response(200, json={"value": [{"__id": "two"}]})
        return httpx.Response(404)

    async def exercise() -> list[tuple[list[dict[str, object]], str | None]]:
        central = _client(handler)
        async with central:
            return [
                page
                async for page in central.submission_pages(17, "rainfall")
            ]

    pages = asyncio.run(exercise())
    assert [row["__id"] for page, _ in pages for row in page] == ["one", "two"]
    assert pages[0][1] == (
        "https://central.example.org/v1/projects/17/forms/rainfall.svc/"
        "Submissions?$skiptoken=page-2"
    )
    assert pages[1][1] is None
    assert len(requests) == 3


def test_odata_pagination_rejects_cross_origin_next_link(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"token": "test-token"})
        return httpx.Response(
            200,
            json={
                "value": [],
                "@odata.nextLink": "https://attacker.example.net/steal?cursor=secret",
            },
        )

    async def exercise() -> None:
        central = _client(handler)
        async with central:
            async for _ in central.submission_pages(17, "rainfall"):
                pass

    with pytest.raises(ValueError, match="outside the configured server"):
        asyncio.run(exercise())
