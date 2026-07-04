"""M4 on-sky focus tests: the HFD/peak star metric, luma-plane analysis, mode + zoom endpoints.

The real V-curve is a hardware "Done when" (rack a focuser through focus). Here we prove the metric
*moves the right way* on synthetic stars — a tighter star must read a smaller HFD and a higher peak
— which is the whole guarantee the on-sky V-curve relies on.
"""

from __future__ import annotations

import numpy as np
from litestar.testing import TestClient

from app.camera import focus
from app.camera.mock import MockCamera
from app.main import app


def _gaussian_star(
    sigma: float, size: int = 80, flux: float = 5000.0, bg: float = 10.0
) -> np.ndarray:
    """A star of fixed total flux spread over ``sigma`` — defocus widens sigma, lowering the peak."""
    y, x = np.indices((size, size))
    c = size / 2
    amp = flux / (2 * np.pi * sigma**2)
    g = amp * np.exp(-((x - c) ** 2 + (y - c) ** 2) / (2 * sigma**2))
    return (g + bg).clip(0, 255).astype(np.uint8)


def test_hfd_shrinks_and_peak_rises_toward_focus() -> None:
    tight = focus.analyze_luma(_gaussian_star(sigma=2.0), mode="star")
    loose = focus.analyze_luma(_gaussian_star(sigma=6.0), mode="star")

    assert tight["star_found"] and loose["star_found"]
    assert tight["hfd"] < loose["hfd"]  # sharper focus → smaller half-flux diameter
    assert tight["peak"] > loose["peak"]  # flux concentrated → brighter core
    assert tight["focus_metric"] == "HFD"
    assert tight["focus_direction"] == "lower"  # minimize HFD


def test_star_metrics_handles_empty_region() -> None:
    """A zero-size region must return 'no star' quietly, not warn + raise inside the guard."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # turn any numpy RuntimeWarning into a failure
        result = focus._star_metrics(np.empty((0, 0), dtype=np.float32))
    assert result["found"] is False
    assert result["hfd"] == 0.0


def test_star_mode_reports_no_star_on_empty_sky() -> None:
    rng = np.random.default_rng(0)
    sky = rng.normal(8.0, 2.0, size=(80, 80)).clip(0, 255).astype(np.uint8)
    result = focus.analyze_luma(sky, mode="star")
    assert result["star_found"] is False
    assert result["hfd"] == 0.0


def test_scene_mode_still_uses_laplacian() -> None:
    rng = np.random.default_rng(1)
    detail = rng.integers(0, 256, size=(80, 80)).astype(np.uint8)
    flat = np.full((80, 80), 128, dtype=np.uint8)
    assert focus.analyze_luma(detail, mode="scene")["focus_score"] > 0
    assert focus.analyze_luma(flat, mode="scene")["focus_score"] == 0
    assert focus.analyze_luma(detail, mode="scene")["focus_metric"] == "Laplacian"


def test_mock_synthesizes_a_luma_plane() -> None:
    cam = MockCamera(200, 150)
    assert cam.get_luma() is None  # nothing rendered yet
    cam._render(0.0)
    luma = cam.get_luma()
    assert luma is not None
    assert luma.shape == (150, 200)  # (h, w), 2D grayscale — not a decoded JPEG
    assert cam.supports_hw_zoom is False


def test_focus_mode_endpoint_switches_metric() -> None:
    with TestClient(app=app) as client:
        # Star is the night default.
        assert client.get("/api/focus").json()["mode"] == "star"

        assert client.post("/api/focus/mode", json={"mode": "scene"}).json()["mode"] == "scene"
        assert client.get("/api/focus").json()["mode"] == "scene"

        # An unknown mode is rejected by validation.
        assert client.post("/api/focus/mode", json={"mode": "bogus"}).status_code == 400

        client.post("/api/focus/mode", json={"mode": "star"})  # restore default


def test_zoom_endpoint_is_noop_on_mock() -> None:
    with TestClient(app=app) as client:
        resp = client.post("/api/focus/zoom", json={"roi": [0.4, 0.4, 0.6, 0.6]})
        body = resp.json()
        assert body["roi"] == [0.4, 0.4, 0.6, 0.6]
        assert body["hw_zoom"] is False  # mock has no sensor to crop
        assert client.post("/api/focus/zoom", json={"roi": None}).json()["roi"] is None


def test_live_ws_carries_star_metrics() -> None:
    with TestClient(app=app) as client:
        with client.websocket_connect("/api/live") as ws:
            msg = ws.receive_json()
            assert msg["focus_mode"] in ("star", "scene")
            assert "hfd" in msg
            assert "focus_direction" in msg
