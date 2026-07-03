"""The single owner of the sensor.

Holds the active driver, the frame broker, and a lock that will serialize capture/mode-switch
operations against the preview (M4). For M0 it simply starts the mock preview.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import anyio

from ..config import Settings
from . import focus, settings as camsettings
from .base import Camera
from .mock import MockCamera
from .profile import CameraProfile
from .settings import CameraSettings
from .stream import FrameBroker

logger = logging.getLogger(__name__)


def select_camera(settings: Settings) -> Camera:
    """Pick a driver: the real one if picamera2 imports and isn't forced off, else the mock."""
    if settings.force_mock:
        logger.info("PFC_FORCE_MOCK set — using MockCamera")
        return MockCamera(settings.mock_width, settings.mock_height, settings.mock_fps)
    try:
        from .picamera2_driver import Picamera2Camera  # noqa: PLC0415 (optional, Pi-only)

        camera = Picamera2Camera(settings.preview_width, settings.preview_height)
        logger.info("picamera2 available — using Picamera2Camera")
        return camera
    except Exception as exc:  # ImportError on dev boxes, RuntimeError if no camera present
        logger.info("Falling back to MockCamera (%s)", exc)
        return MockCamera(settings.mock_width, settings.mock_height, settings.mock_fps)


class CameraManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.db_path = settings.db_path
        self.camera: Camera = select_camera(settings)
        self.broker = FrameBroker()
        self.lock = asyncio.Lock()  # serializes capture / mode switches (M4)
        self.started = False

        # Focus assist. Star mode (HFD) is the night default — the app's on-sky reason to exist.
        self.focus_hz = settings.focus_hz
        self.focus_roi: focus.ROI | None = None
        self.focus_mode = "star"
        self.metrics: dict = {"focus_score": 0.0, "histogram": [], "clipping": 0.0, "roi": None}
        self._analyze_task: asyncio.Task | None = None

        # Camera controls (validated, sensor-agnostic)
        self.settings = CameraSettings()

    @property
    def profile(self) -> CameraProfile:
        return self.camera.profile

    def set_focus_roi(self, roi: focus.ROI | None) -> None:
        self.focus_roi = roi

    def set_focus_mode(self, mode: str) -> str:
        """Switch the metric between 'scene' (Laplacian) and 'star' (HFD); ignores unknown modes."""
        if mode in ("scene", "star"):
            self.focus_mode = mode
        return self.focus_mode

    async def set_zoom(self, roi: focus.ROI | None) -> None:
        """Ask the driver for a true 1:1 sensor crop (no-op on the mock, which zooms in CSS)."""
        await self.camera.set_zoom(roi)

    async def start(self) -> None:
        await self.camera.start(self.broker)
        self.started = True
        # Push the initial settings so the driver has a defined baseline (frame duration, AE, ...).
        self.settings = camsettings.clamp(self.settings, self.profile)
        await self.camera.set_controls(camsettings.to_controls(self.settings))
        self._analyze_task = asyncio.create_task(self._analyze_loop())
        logger.info("Camera started: %s", self.profile.model)

    async def apply_settings(self, update: dict) -> CameraSettings:
        """Validate a partial settings update against the sensor and apply it to the driver."""
        merged = camsettings.merge(self.settings, update)
        merged = camsettings.clamp(merged, self.profile)
        await self.camera.set_controls(camsettings.to_controls(merged))
        self.settings = merged
        logger.info("Applied settings: %s", merged.as_dict())
        return merged

    async def stop(self) -> None:
        if self._analyze_task is not None:
            self._analyze_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._analyze_task
            self._analyze_task = None
        await self.camera.stop()
        self.started = False
        logger.info("Camera stopped")

    async def _analyze_loop(self) -> None:
        """Compute focus/histogram metrics off the newest preview frame, throttled.

        The luma fetch + numpy is CPU-bound (and the real driver's capture blocks), so it runs in a
        worker thread. A freshly published JPEG is the "new frame" signal; if analysis can't keep
        up, frames are simply skipped.
        """
        interval = 1.0 / max(self.focus_hz, 1)
        last_frame: bytes | None = None
        while True:
            frame = self.broker.latest
            if frame is not None and frame is not last_frame:
                last_frame = frame
                try:
                    self.metrics = await anyio.to_thread.run_sync(
                        self._compute_metrics, frame, self.focus_roi, self.focus_mode
                    )
                except Exception:  # noqa: BLE001 - never let analysis kill the loop
                    logger.exception("Focus analysis failed")
            await asyncio.sleep(interval)

    def _compute_metrics(self, frame: bytes, roi: focus.ROI | None, mode: str) -> dict:
        """Analyze the driver's luma plane if it has one, else fall back to decoding the JPEG."""
        luma = self.camera.get_luma()
        if luma is not None:
            return focus.analyze_luma(luma, roi, mode)
        return focus.analyze(frame, roi, mode)

    async def get_controls(self) -> dict:
        return await self.camera.get_controls()

    async def set_controls(self, values: dict) -> None:
        await self.camera.set_controls(values)
