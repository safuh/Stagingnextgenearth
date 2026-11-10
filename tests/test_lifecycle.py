from fastapi.testclient import TestClient

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Settings


def test_startup_initializes_database_resources() -> None:
    settings = Settings.for_profile("test")
    app = create_app(settings)

    with TestClient(app):
        assert app.state.startup_complete is True
        assert app.state.db_engine is not None
        assert app.state.db_session_factory is not None

    assert app.state.startup_complete is False


def test_liveness_does_not_require_database() -> None:
    settings = Settings.for_profile("test")
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
