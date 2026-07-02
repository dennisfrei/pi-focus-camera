"""Focus-assist tests: the sharpness metric and the ROI endpoint (no hardware)."""

from __future__ import annotations

import io

import numpy as np
from litestar.testing import TestClient
from PIL import Image

from app.camera import focus
from app.main import app


def _jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), mode="L").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_sharp_image_scores_higher_than_blurry() -> None:
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 256, size=(240, 320))  # high-frequency detail = sharp
    sharp = _jpeg(noise)
    flat = _jpeg(np.full((240, 320), 128))  # uniform = no detail

    assert focus.analyze(sharp)["focus_score"] > focus.analyze(flat)["focus_score"]


def test_histogram_length_and_clipping() -> None:
    white = _jpeg(np.full((100, 100), 255))
    result = focus.analyze(white)
    assert len(result["histogram"]) == focus.HIST_BINS
    assert result["clipping"] > 0.9  # nearly all pixels are blown out


def test_roi_falls_back_when_degenerate() -> None:
    img = _jpeg(np.full((100, 100), 128))
    # A zero-area ROI should not crash; analysis falls back to the full frame.
    result = focus.analyze(img, roi=(0.5, 0.5, 0.5, 0.5))
    assert "focus_score" in result


def test_roi_endpoint_roundtrip() -> None:
    with TestClient(app=app) as client:
        resp = client.post("/api/focus/roi", json={"roi": [0.1, 0.1, 0.6, 0.6]})
        assert resp.json()["roi"] == [0.1, 0.1, 0.6, 0.6]
        # Clearing it returns to full-frame.
        assert client.post("/api/focus/roi", json={"roi": None}).json()["roi"] is None


def test_live_metrics_present_after_startup() -> None:
    with TestClient(app=app) as client:
        with client.websocket_connect("/api/live") as ws:
            msg = ws.receive_json()
            assert "focus_score" in msg
            assert "histogram" in msg
