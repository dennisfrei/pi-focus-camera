"""M6 tests: the intervalometer (run to completion + cancel) and real system metrics."""

from __future__ import annotations

import asyncio
from pathlib import Path

from litestar.testing import TestClient

from app.camera.manager import CameraManager
from app.config import Settings
from app.controllers import system
from app.storage import captures


async def _manager(tmp_path: Path) -> CameraManager:
    settings = Settings(db_path=tmp_path / "s.db", captures_dir=tmp_path / "caps")
    await captures.init_db(settings.db_path)
    manager = CameraManager(settings)
    await manager.start()
    # Short exposures so the sequence runs fast.
    await manager.apply_settings({"ae_enable": False, "exposure_us": 10_000})
    return manager


async def test_sequence_runs_to_completion(tmp_path: Path) -> None:
    manager = await _manager(tmp_path)
    try:
        manager.start_sequence(count=3, interval_s=0.05)
        assert manager.sequence_state["active"] is True

        for _ in range(100):  # wait up to ~5 s for completion
            if not manager.sequence_state["active"]:
                break
            await asyncio.sleep(0.05)

        assert manager.sequence_state["active"] is False
        assert manager.sequence_state["done"] == 3
        assert len(await captures.list_captures(manager.db_path)) == 3
    finally:
        await manager.stop()


async def test_sequence_can_be_cancelled(tmp_path: Path) -> None:
    manager = await _manager(tmp_path)
    try:
        # Long interval so it's still running when we cancel after the first frame.
        manager.start_sequence(count=10, interval_s=5.0)
        await asyncio.sleep(0.3)
        assert manager.cancel_sequence() is True

        for _ in range(40):
            if not manager.sequence_state["active"]:
                break
            await asyncio.sleep(0.05)

        assert manager.sequence_state["active"] is False
        assert manager.sequence_state["done"] < 10  # stopped early
        assert manager.cancel_sequence() is False  # nothing running now
    finally:
        await manager.stop()


async def test_rejects_second_sequence(tmp_path: Path) -> None:
    manager = await _manager(tmp_path)
    try:
        manager.start_sequence(count=5, interval_s=1.0)
        try:
            manager.start_sequence(count=2, interval_s=0.0)
            raise AssertionError("should refuse a concurrent sequence")
        except RuntimeError:
            pass
    finally:
        manager.cancel_sequence()
        await manager.stop()


def test_sequence_endpoints(client: TestClient) -> None:
    started = client.post("/api/sequence", json={"count": 2, "interval_s": 5.0}).json()
    assert started["active"] is True and started["count"] == 2
    # A second start while running is a 400.
    assert client.post("/api/sequence", json={"count": 2, "interval_s": 0}).status_code == 400
    assert client.post("/api/sequence/cancel").json()["cancelled"] is True


def test_power_controls_disabled_by_default(client: TestClient) -> None:
    """Power off/reboot must be refused (403) unless explicitly enabled, and bad actions are 400."""
    assert client.get("/api/system").json()["power_controls"] is False
    assert client.post("/api/system/power", json={"action": "shutdown"}).status_code == 403
    assert client.post("/api/system/power", json={"action": "melt"}).status_code == 400


def test_power_controls_flag_follows_settings(power_client: TestClient) -> None:
    """The factory-injected settings drive the flag — GET only (never POST the real power action)."""
    assert power_client.get("/api/system").json()["power_controls"] is True


def test_system_metrics_shape(client: TestClient) -> None:
    # The values may be None on a non-Pi dev box, but the keys and disk shape must be present.
    assert system.disk_usage(Path("/")).keys() == {"total", "used", "free"}
    data = client.get("/api/system").json()
    assert "cpu_temp_c" in data
    assert "uptime_s" in data
    assert set(data["disk"]) == {"total", "used", "free"}
    assert data["disk"]["total"] > 0
