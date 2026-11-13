from fastapi.testclient import TestClient

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Settings


def make_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        cors_origins=["https://example.com"],
    )


def test_health_endpoint() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_id_is_generated_and_returned() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_valid_request_id_is_propagated() -> None:
    request_id = "2f3b5b74-6a89-4e8e-a1b0-8e4ef1c4f9b1"
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "not-a-uuid"})

    assert response.headers["X-Request-ID"] != "not-a-uuid"


def test_not_found_uses_error_envelope() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_cors_policy_is_explicit() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.com"


def test_validation_errors_use_safe_serializable_details() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.post(
            "/api/auth/register",
            json={"identifier": "", "password": ""},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
    assert all("input" not in item and "ctx" not in item for item in body["error"]["details"])



def test_clamav_scanner_is_wired_only_when_enabled() -> None:
    from stagingnextgenearth.scanning import ClamAVScanner

    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        object_storage_enabled=True,
        object_storage_bucket="private-research",
        object_storage_access_key_id="test-access",
        object_storage_secret_access_key="test-secret",
        malware_scanning_enabled=True,
        clamav_host="clamav.internal",
    )

    app = create_app(settings)

    assert isinstance(app.state.dataset_file_scanner, ClamAVScanner)
