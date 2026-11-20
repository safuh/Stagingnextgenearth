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
        seen.append(
            (
                request.method,
                request.url.raw_path.decode("ascii"),
                request.headers.get("Authorization"),
            )
        )
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


def test_odata_pagination_follows_same_origin_next_link() -> None:
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
            return [page async for page in central.submission_pages(17, "rainfall")]

    pages = asyncio.run(exercise())
    assert [row["__id"] for page, _ in pages for row in page] == ["one", "two"]
    assert pages[0][1] == (
        "https://central.example.org/v1/projects/17/forms/rainfall.svc/"
        "Submissions?$skiptoken=page-2"
    )
    assert pages[1][1] is None
    assert len(requests) == 4  # session creation + two pages + session revocation
    assert requests[-1].endswith("/v1/sessions/test-token")


def test_odata_pagination_rejects_cross_origin_next_link() -> None:
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


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_central_read_retries_transient_status_and_honours_retry_after(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    requests = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("stagingnextgenearth.workers.odk_sync.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        if request.method == "POST":
            return httpx.Response(200, json={"token": "retry-token"})
        if request.method == "DELETE":
            return httpx.Response(204)
        requests += 1
        if requests == 1:
            return httpx.Response(status_code, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[{"xmlFormId": "rainfall-v1"}])

    async def exercise() -> list[dict[str, object]]:
        central = _client(handler)
        async with central:
            return await central.list_forms(17)

    assert asyncio.run(exercise()) == [{"xmlFormId": "rainfall-v1"}]
    assert requests == 2
    assert delays == [0.0]


def test_central_read_retries_transient_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("stagingnextgenearth.workers.odk_sync.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        if request.method == "POST":
            return httpx.Response(200, json={"token": "retry-token"})
        if request.method == "DELETE":
            return httpx.Response(204)
        requests += 1
        if requests == 1:
            raise httpx.ConnectError("temporary connection issue", request=request)
        return httpx.Response(200, json=[{"xmlFormId": "rainfall-v1"}])

    async def exercise() -> list[dict[str, object]]:
        central = _client(handler)
        async with central:
            return await central.list_forms(17)

    assert asyncio.run(exercise()) == [{"xmlFormId": "rainfall-v1"}]
    assert requests == 2
    assert delays == [0.25]


def test_central_read_does_not_retry_authentication_or_permission_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("stagingnextgenearth.workers.odk_sync.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        if request.method == "POST":
            return httpx.Response(200, json={"token": "retry-token"})
        if request.method == "DELETE":
            return httpx.Response(204)
        requests += 1
        return httpx.Response(403)

    async def exercise() -> None:
        central = _client(handler)
        async with central:
            await central.list_forms(17)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(exercise())
    assert requests == 1
    assert delays == []


def test_central_read_stops_after_bounded_retry_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("stagingnextgenearth.workers.odk_sync.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        if request.method == "POST":
            return httpx.Response(200, json={"token": "retry-token"})
        if request.method == "DELETE":
            return httpx.Response(204)
        requests += 1
        return httpx.Response(503)

    async def exercise() -> None:
        central = _client(handler)
        async with central:
            await central.list_forms(17)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(exercise())
    assert requests == 4
    assert delays == [0.25, 0.5, 1.0]
