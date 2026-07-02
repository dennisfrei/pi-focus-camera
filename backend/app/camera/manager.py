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
from . import focus
from .base import Camera
from .mock import MockCamera
from .profile import CameraProfile
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
        self.camera: Camera = select_camera(settings)
        self.broker = FrameBroker()
        self.lock = asyncio.Lock()  # serializes capture / mode switches (M4)
        self.started = False

        # Focus assist
        self.focus_hz = settings.focus_hz
        self.focus_roi: focus.ROI | None = None
        self.metrics: dict = {"focus_score": 0.0, "histogram": [], "clipping": 0.0, "roi": None}
        self._analyze_task: asyncio.Task | None = None

    @property
    def profile(self) -> CameraProfile:
        return self.camera.profile

    def set_focus_roi(self, roi: focus.ROI | None) -> None:
        self.focus_roi = roi

    async def start(self) -> None:
        await self.camera.start(self.broker)
        self.started = True
        self._analyze_task = asyncio.create_task(self._analyze_loop())
        logger.info("Camera started: %s", self.profile.model)

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

        Decoding + numpy is CPU-bound, so it runs in a worker thread to keep the event loop free.
        Only whole new frames are analyzed; if analysis can't keep up, frames are simply skipped.
        """
        interval = 1.0 / max(self.focus_hz, 1)
        last_frame: bytes | None = None
        while True:
            frame = self.broker.latest
            if frame is not None and frame is not last_frame:
                last_frame = frame
                try:
                    self.metrics = await anyio.to_thread.run_sync(
                        focus.analyze, frame, self.focus_roi
                    )
                except Exception:  # noqa: BLE001 - never let analysis kill the loop
                    logger.exception("Focus analysis failed")
            await asyncio.sleep(interval)

    async def get_controls(self) -> dict:
        return await self.camera.get_controls()

    async def set_controls(self, values: dict) -> None:
        await self.camera.set_controls(values)
