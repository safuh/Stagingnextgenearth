"""Exercise the real ODK HTTP client against the loopback-only demo server."""

import asyncio
import threading

import pytest

from scripts.run_odk_mock_central import build_server
from stagingnextgenearth.workers.odk_sync import ODKCentralClient


def test_mock_central_supports_auth_forms_pagination_and_revocation() -> None:
    server = build_server(port=0, page_size=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    async def exercise() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        async with ODKCentralClient(
            base_url, "odk-demo@example.test", "local-demo-only"
        ) as central:
            forms = await central.list_forms(22)
            pages = [
                page
                async for page, _ in central.submission_pages(22, "nextgen_climate_observation")
            ]
            return forms, [row for page in pages for row in page]

    try:
        forms, rows = asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert forms[0]["xmlFormId"] == "nextgen_climate_observation"
    assert [row["__id"] for row in rows] == [
        "uuid:nextgen-demo-0001",
        "uuid:nextgen-demo-0002",
    ]


def test_mock_central_refuses_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="loopback only"):
        build_server(host="0.0.0.0")
