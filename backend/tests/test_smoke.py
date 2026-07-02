"""M0 smoke tests — exercise the app against the mock camera, no hardware."""

from __future__ import annotations

from litestar.testing import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app=app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_system_reports_mock() -> None:
    with TestClient(app=app) as client:
        data = client.get("/api/system").json()
        assert data["mock"] is True
        assert data["profile"]["exposure_us"]["max"] > 0


def test_settings_roundtrip() -> None:
    with TestClient(app=app) as client:
        client.patch("/api/camera/settings", json={"AnalogueGain": 4.0})
        controls = client.get("/api/camera/settings").json()["controls"]
        assert controls["AnalogueGain"] == 4.0


def test_openapi_schema() -> None:
    with TestClient(app=app) as client:
        schema = client.get("/api/docs/openapi.json").json()
        assert schema["info"]["title"] == "Prime Focus Camera API"
        assert "/api/system" in schema["paths"]


def test_swagger_docs_are_offline() -> None:
    """The docs page must reference only vendored assets — no CDN (the Pi is offline)."""
    with TestClient(app=app) as client:
        html = client.get("/api/docs").text
        assert "/vendor/swagger/swagger-ui-bundle.js" in html
        for cdn in ("jsdelivr", "unpkg", "cdn.redoc"):
            assert cdn not in html
