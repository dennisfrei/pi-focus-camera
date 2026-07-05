"""M5 capture tests: storage + files, the capture→gallery→delete flow, raw, and long-exp progress.

The on-Pi "Done when" (a real long exposure that pauses the sensor) needs hardware; here we drive the
whole path against the mock — files written, DB row, thumbnail served, download, delete, and a
time-based progress countdown that goes active then clears.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

from litestar.testing import TestClient
from PIL import Image

from app.camera.base import CaptureResult
from app.camera.manager import CameraManager
from app.config import Settings
from app.storage import captures


def _jpeg(w: int = 120, h: int = 90) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 60, 90)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_storage_write_and_crud(tmp_path: Path) -> None:
    db = tmp_path / "caps.db"
    caps_dir = tmp_path / "captures"
    await captures.init_db(db)

    result = CaptureResult(jpeg=_jpeg(), width=120, height=90, raw=b"rawbytes", raw_ext="png")
    row = captures.write_files(caps_dir, result, {"gain": 2.0, "exposure_us": 5000})

    # Files landed on disk: jpeg, thumbnail, raw.
    assert (caps_dir / row["jpeg_path"]).exists()
    assert (caps_dir / row["thumb_path"]).exists()
    assert (caps_dir / row["raw_path"]).exists()

    capture_id = await captures.add_capture(db, row)
    listed = await captures.list_captures(db)
    assert len(listed) == 1
    assert listed[0]["id"] == capture_id
    assert listed[0]["has_raw"] is True
    assert listed[0]["settings"]["gain"] == 2.0

    removed = await captures.delete_capture(db, capture_id)
    assert removed is not None
    assert await captures.get_capture(db, capture_id) is None
    assert await captures.delete_capture(db, capture_id) is None  # already gone


def test_capture_endpoint_roundtrip(client: TestClient) -> None:
    created = client.post("/api/capture", json={"raw": False, "exposure_us": 15000}).json()
    cid = created["id"]
    assert created["width"] > 0 and created["height"] > 0
    assert created["has_raw"] is False

    listing = client.get("/api/gallery").json()["captures"]
    assert [c["id"] for c in listing] == [cid]

    assert client.get(f"/api/gallery/{cid}/thumb").status_code == 200
    img = client.get(f"/api/gallery/{cid}/image")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg"
    # No raw was requested.
    assert client.get(f"/api/gallery/{cid}/raw").status_code == 404

    assert client.delete(f"/api/gallery/{cid}").status_code == 200
    assert client.get(f"/api/gallery/{cid}/image").status_code == 404  # gone afterwards


def test_capture_with_raw(client: TestClient) -> None:
    created = client.post("/api/capture", json={"raw": True, "exposure_us": 15000}).json()
    cid = created["id"]
    assert created["has_raw"] is True
    raw = client.get(f"/api/gallery/{cid}/raw")
    assert raw.status_code == 200
    assert "attachment" in raw.headers.get("content-disposition", "")


async def test_capture_restores_preview_settings(tmp_path: Path) -> None:
    """After a capture the driver's controls must still reflect the live settings, not defaults."""
    settings = Settings(db_path=tmp_path / "s.db", captures_dir=tmp_path / "caps")
    await captures.init_db(settings.db_path)
    manager = CameraManager(settings)
    await manager.start()
    try:
        await manager.apply_settings(
            {"ae_enable": False, "exposure_us": 1_500_000, "preview_mode": "star"}
        )
        before = manager.camera._controls.get("FrameDurationLimits")
        await manager.capture(raw=False)
        after = manager.camera._controls.get("FrameDurationLimits")
        assert after == before  # star cadence survived the capture, not reverted to video rate
        assert after == (1_500_000, 1_500_000)
    finally:
        await manager.stop()


async def test_capture_can_be_cancelled(tmp_path: Path) -> None:
    """A long single capture can be aborted; it returns None and writes no gallery row."""
    settings = Settings(db_path=tmp_path / "s.db", captures_dir=tmp_path / "caps")
    await captures.init_db(settings.db_path)
    manager = CameraManager(settings)
    await manager.start()
    try:
        await manager.apply_settings({"ae_enable": False, "exposure_us": 3_000_000})  # 3 s
        task = asyncio.create_task(manager.capture())
        await asyncio.sleep(0.2)
        assert manager.capture_state["active"] is True
        assert manager.cancel_capture() is True

        result = await task
        assert result is None  # cancelled → no record
        assert manager.capture_state["active"] is False
        assert await captures.list_captures(manager.db_path) == []  # nothing written
        assert manager.cancel_capture() is False  # nothing running now
    finally:
        await manager.stop()


def test_capture_cancel_endpoint_when_idle(client: TestClient) -> None:
    assert client.post("/api/capture/cancel").json() == {"cancelled": False}


async def test_long_exposure_reports_progress(tmp_path: Path) -> None:
    settings = Settings(db_path=tmp_path / "t.db", captures_dir=tmp_path / "caps")
    await captures.init_db(settings.db_path)
    manager = CameraManager(settings)
    await manager.start()
    try:
        await manager.apply_settings({"ae_enable": False, "exposure_us": 500_000})  # 0.5 s
        task = asyncio.create_task(manager.capture())

        await asyncio.sleep(0.2)  # mid-exposure
        assert manager.capture_state["active"] is True
        assert 0.0 < manager.capture_state["progress"] < 1.0
        assert manager.capture_state["remaining_s"] > 0.0

        record = await task
        assert manager.capture_state["active"] is False
        assert record["id"] >= 1
        assert (settings.captures_dir / record["jpeg_path"]).exists()
    finally:
        await manager.stop()
