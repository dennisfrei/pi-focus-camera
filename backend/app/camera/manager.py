"""The single owner of the sensor.

Holds the active driver, the frame broker, the focus-analysis loop, the validated camera settings,
and a lock that serializes captures/mode-switches against the preview (one sensor can't stream and
integrate a long exposure at once).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import anyio

from ..config import Settings
from ..storage import captures
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
        # The driver is built in start() (off the event loop) — constructing Picamera2 on hardware
        # blocks for a moment, which we don't want to do synchronously during app startup.
        self._camera: Camera | None = None
        self.broker = FrameBroker()
        self.lock = asyncio.Lock()  # serializes captures / mode switches against the preview
        self.started = False

        # Focus assist. Star mode (HFD) is the night default — the app's on-sky reason to exist.
        self.focus_hz = settings.focus_hz
        self.focus_roi: focus.ROI | None = None
        self.focus_mode = "star"
        self._zoom_roi: focus.ROI | None = None  # active hardware crop, re-applied after a capture
        self.metrics: dict = {"focus_score": 0.0, "histogram": [], "clipping": 0.0, "roi": None}
        self._analyze_task: asyncio.Task | None = None
        # Connected /api/live WebSocket clients — the only consumer of the focus metrics. When 0,
        # the analyze loop skips its work (idle CPU/heat saving on the Pi).
        self.live_clients = 0

        # Camera controls (validated, sensor-agnostic)
        self.settings = CameraSettings()

        # Capture (M5). A single still or long exposure; progress is pushed over the WS.
        self.captures_dir = settings.captures_dir
        self.capture_state: dict = {
            "active": False,
            "progress": 0.0,
            "remaining_s": 0.0,
            "exposure_us": 0,
            "raw": False,
        }
        self._capture_task: asyncio.Task | None = None

        # Sequence / intervalometer (M6). N frames × exposure × interval; cancelable.
        self.sequence_state: dict = {
            "active": False,
            "count": 0,
            "done": 0,
            "interval_s": 0.0,
            "exposure_us": 0,
            "raw": False,
        }
        self._sequence_task: asyncio.Task | None = None

    @property
    def camera(self) -> Camera:
        if self._camera is None:
            raise RuntimeError("camera manager not started")
        return self._camera

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
        """Ask the driver for a true 1:1 sensor crop (no-op on the mock, which zooms in CSS).

        Serialized against capture, and — on hardware — the full-frame focus ROI is dropped: once
        ScalerCrop makes the streamed frame *be* the region, a full-frame ROI would double-crop it.
        """
        async with self.lock:
            await self.camera.set_zoom(roi)
            self._zoom_roi = roi
            if self.profile.supports_hw_zoom:
                self.focus_roi = None

    async def capture(
        self, raw: bool = False, exposure_us: int | None = None, frame_type: str = "light"
    ) -> dict | None:
        """Capture a single still, cancelably. Returns the gallery record, or None if cancelled.

        The work runs as a tracked task so ``cancel_capture`` can abort a long exposure (e.g. a
        mis-framed 200 s sub) without waiting it out. Sequences call :meth:`_do_capture` directly so
        cancelling one frame doesn't tear down the whole run.
        """
        task = asyncio.create_task(self._do_capture(raw, exposure_us, frame_type))
        self._capture_task = task
        try:
            return await task
        except asyncio.CancelledError:
            logger.info("Capture cancelled")
            return None
        finally:
            self._capture_task = None

    def cancel_capture(self) -> bool:
        """Abort the in-progress single capture; returns whether one was running."""
        if self._capture_task is not None and not self._capture_task.done():
            self._capture_task.cancel()
            return True
        return False

    async def _do_capture(
        self, raw: bool, exposure_us: int | None, frame_type: str = "light"
    ) -> dict:
        """Capture a still (JPEG + optional raw), store it, and return its gallery record.

        The lock serializes captures against each other and against mode switches. For a long
        exposure the preview is paused for the duration; a time-based progress countdown is pushed
        over the WS from ``capture_state`` while the (blocking) capture runs.
        """
        async with self.lock:
            exp = int(exposure_us) if exposure_us else int(self.settings.exposure_us)
            gain = float(self.settings.gain)
            snapshot = {
                **self.settings.as_dict(),
                "exposure_us": exp,
                "raw": raw,
                "frame_type": frame_type,
            }
            self.capture_state = {
                "active": True,
                "progress": 0.0,
                "remaining_s": exp / 1_000_000,
                "exposure_us": exp,
                "raw": raw,
            }
            progress = asyncio.create_task(self._run_progress(exp))
            try:
                result = await self.camera.capture_still(exp, gain, raw, self.settings.ae_enable)
            finally:
                progress.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await progress
                self.capture_state = {**self.capture_state, "active": False, "remaining_s": 0.0}
                # The driver reconfigured the sensor for the still and restarted a *default* preview;
                # re-apply the live settings (exposure/gain/mode) and any zoom so it doesn't silently
                # revert to 30 fps auto-exposure. Direct driver calls — we already hold the lock.
                await self.camera.set_controls(camsettings.to_controls(self.settings))
                if self._zoom_roi is not None:
                    await self.camera.set_zoom(self._zoom_roi)

            row = await anyio.to_thread.run_sync(
                captures.write_files, self.captures_dir, result, snapshot
            )
            capture_id = await captures.add_capture(self.db_path, row)
            logger.info(
                "Captured #%s (%dx%d, raw=%s)", capture_id, result.width, result.height, raw
            )
            return await captures.get_capture(self.db_path, capture_id)  # type: ignore[return-value]

    async def _run_progress(self, exposure_us: int) -> None:
        """Advance ``capture_state`` from a time estimate while the capture blocks."""
        loop = asyncio.get_running_loop()
        dur = max(exposure_us / 1_000_000, 0.001)
        start = loop.time()
        while True:
            elapsed = loop.time() - start
            self.capture_state["progress"] = min(0.99, elapsed / dur)
            self.capture_state["remaining_s"] = max(0.0, dur - elapsed)
            await asyncio.sleep(0.1)

    def start_sequence(
        self,
        count: int,
        interval_s: float,
        exposure_us: int | None = None,
        raw: bool = False,
        frame_type: str = "light",
    ) -> dict:
        """Kick off an N-frame intervalometer run in the background; returns the initial state."""
        if self.sequence_state["active"]:
            raise RuntimeError("a sequence is already running")
        exp = int(exposure_us) if exposure_us else int(self.settings.exposure_us)
        self.sequence_state = {
            "active": True,
            "count": count,
            "done": 0,
            "interval_s": interval_s,
            "exposure_us": exp,
            "raw": raw,
            "frame_type": frame_type,
        }
        self._sequence_task = asyncio.create_task(
            self._run_sequence(count, interval_s, exp, raw, frame_type)
        )
        return dict(self.sequence_state)

    async def _run_sequence(
        self, count: int, interval_s: float, exposure_us: int, raw: bool, frame_type: str
    ) -> None:
        loop = asyncio.get_running_loop()
        try:
            for i in range(count):
                # Start-to-start cadence: the interval is measured from when each frame *begins*,
                # so a capture that overruns the interval just starts the next one immediately —
                # what an astro intervalometer means by "interval".
                frame_start = loop.time()
                await self._do_capture(raw=raw, exposure_us=exposure_us, frame_type=frame_type)
                self.sequence_state = {**self.sequence_state, "done": i + 1}
                if i < count - 1:
                    await asyncio.sleep(max(0.0, interval_s - (loop.time() - frame_start)))
        except asyncio.CancelledError:
            pass  # cancel_sequence stops it between/within frames
        finally:
            self.sequence_state = {**self.sequence_state, "active": False}

    def cancel_sequence(self) -> bool:
        """Cancel a running sequence; returns whether one was actually running."""
        if self._sequence_task is not None and not self._sequence_task.done():
            self._sequence_task.cancel()
            return True
        return False

    async def start(self) -> None:
        # Build the driver off-thread — Picamera2() blocks briefly on real hardware.
        self._camera = await anyio.to_thread.run_sync(select_camera, self._settings)
        await self.camera.start(self.broker)
        self.started = True
        # Push the initial settings so the driver has a defined baseline (frame duration, AE, ...).
        self.settings = camsettings.clamp(self.settings, self.profile)
        await self.camera.set_controls(camsettings.to_controls(self.settings))
        self._analyze_task = asyncio.create_task(self._analyze_loop())
        logger.info("Camera started: %s", self.profile.model)

    async def apply_settings(self, update: dict) -> CameraSettings:
        """Validate a partial settings update against the sensor and apply it to the driver.

        Held under the lock so it can't push controls to the sensor while a capture has it
        reconfigured (which would raise on the real driver or corrupt the shot).
        """
        async with self.lock:
            merged = camsettings.merge(self.settings, update)
            merged = camsettings.clamp(merged, self.profile)
            # A preview-mode change may need the stream reconfigured (star preview needs a wide
            # frame-duration envelope, or the long exposure is silently clamped) — do it before
            # pushing the per-frame controls so the new range is already permitted.
            if merged.preview_mode != self.settings.preview_mode:
                lo, hi = camsettings.frame_duration_envelope(merged, self.profile)
                await self.camera.set_frame_duration_envelope(lo, hi)
            await self.camera.set_controls(camsettings.to_controls(merged))
            self.settings = merged
            logger.info("Applied settings: %s", merged.as_dict())
            return merged

    async def stop(self) -> None:
        for task in (self._sequence_task, self._capture_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._sequence_task = None
        self._capture_task = None
        if self._analyze_task is not None:
            self._analyze_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._analyze_task
            self._analyze_task = None
        if self._camera is not None:
            await self._camera.stop()
        self.started = False
        logger.info("Camera stopped")

    async def _analyze_loop(self) -> None:
        """Compute focus/histogram metrics off the newest preview frame, throttled.

        The JPEG decode + numpy is CPU-bound, so it runs in a worker thread. A freshly published JPEG
        is the "new frame" signal; if analysis can't keep up, frames are simply skipped. When no live
        client is connected, the metrics feed nothing, so we skip the decode entirely — this is real
        idle CPU/heat saved on the Pi (the metric is only read over the WS).
        """
        interval = 1.0 / max(self.focus_hz, 1)
        last_frame: bytes | None = None
        while True:
            frame = self.broker.latest
            if self.live_clients > 0 and frame is not None and frame is not last_frame:
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
