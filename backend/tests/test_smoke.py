"""M0 smoke tests — exercise the app against the mock camera, no hardware."""

from __future__ import annotations

from litestar.testing import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_system_reports_mock(client: TestClient) -> None:
    data = client.get("/api/system").json()
    assert data["mock"] is True
    assert data["profile"]["exposure_us"]["max"] > 0


def test_settings_roundtrip(client: TestClient) -> None:
    client.patch("/api/camera/settings", json={"gain": 4.0})
    settings = client.get("/api/camera/settings").json()["settings"]
    assert settings["gain"] == 4.0


def test_openapi_schema(client: TestClient) -> None:
    schema = client.get("/api/docs/openapi.json").json()
    assert schema["info"]["title"] == "Prime Focus Camera API"
    assert "/api/system" in schema["paths"]


def test_swagger_docs_are_offline(client: TestClient) -> None:
    """The docs page must reference only vendored assets — no CDN (the Pi is offline)."""
    html = client.get("/api/docs").text
    assert "/vendor/swagger/swagger-ui-bundle.js" in html
    for cdn in ("jsdelivr", "unpkg", "cdn.redoc"):
        assert cdn not in html
