from fastapi import FastAPI
from fastapi.testclient import TestClient

from stagingnextgenearth.core.middleware import PublicClimateRateLimitMiddleware


def test_public_climate_reads_are_rate_limited_per_client_and_organisation() -> None:
    app = FastAPI()
    app.add_middleware(
        PublicClimateRateLimitMiddleware,
        requests=2,
        window_seconds=60,
        api_prefix="/api",
    )

    @app.get("/api/public/organizations/nextgen/climate/overview")
    def public_overview() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/public/organizations/other/climate/overview")
    def other_organisation_overview() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/public/organizations/nextgen/research/publications")
    def public_research() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        first = client.get("/api/public/organizations/nextgen/climate/overview")
        second = client.get("/api/public/organizations/nextgen/climate/overview")
        blocked = client.get("/api/public/organizations/nextgen/climate/overview")
        other_org = client.get("/api/public/organizations/other/climate/overview")
        other_route = client.get("/api/public/organizations/nextgen/research/publications")

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.status_code == 200
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "public_climate_rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.headers["Cache-Control"] == "no-store"
    assert other_org.status_code == 200
    assert other_route.status_code == 200
