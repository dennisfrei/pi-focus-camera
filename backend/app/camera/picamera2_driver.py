"""The real camera driver, backed by picamera2 (libcamera).

This module is imported **only on the Raspberry Pi**. The top-level ``picamera2`` import fails on a
dev box (ImportError) and constructing :class:`Picamera2` fails if no sensor is attached
(RuntimeError) — either way :func:`app.camera.manager.select_camera` catches it and falls back to
:class:`~app.camera.mock.MockCamera`. So constructing this driver doubles as camera detection.

Threading note: picamera2's JPEG encoder calls ``write()`` from its own thread. The frame broker
must be touched on the event-loop thread, so frames are handed over with
``loop.call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import time
from pathlib import Path

import anyio
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

from .base import CaptureResult
from .profile import CameraProfile, build_profile
from .stream import FrameBroker

logger = logging.getLogger(__name__)


class _BrokerOutput(io.BufferedIOBase):
    """A file-like sink for :class:`JpegEncoder`; each ``write`` receives one complete JPEG."""

    def __init__(self, emit) -> None:
        self._emit = emit

    def writable(self) -> bool:
        return True

    def write(self, buf) -> int:  # called from the encoder thread
        self._emit(bytes(buf))
        return len(buf)


class Picamera2Camera:
    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self._w = width
        self._h = height
        self._picam2 = Picamera2()  # raises if no camera present -> manager falls back to mock
        self.profile: CameraProfile = build_profile(self._picam2, (width, height))
        logger.info(
            "Detected %s: max exposure %.1fs, gain up to %.1f",
            self.profile.model,
            self.profile.exposure_us.max / 1_000_000,
            self.profile.gain.max,
        )
        self._controls: dict = {}
        self._broker: FrameBroker | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recording = False

        # Small lores stream for the focus metric (HFD on the brightest star is resolution-tolerant),
        # so it doesn't add much bandwidth alongside the main JPEG stream.
        self._lores_w = min(self._w, 640)
        self._lores_h = int(self._h * self._lores_w / self._w) & ~1  # keep aspect, even for YUV420
        # Latest lores Y plane, grabbed cheaply in the camera callback (never via a separate
        # capture_array, which would contend with the encoder and stall the preview).
        self._latest_luma: np.ndarray | None = None
        self._last_luma_t = 0.0

    async def start(self, broker: FrameBroker) -> None:
        self._broker = broker
        self._loop = asyncio.get_running_loop()
        await anyio.to_thread.run_sync(self._start_sync)

    def _start_sync(self) -> None:
        # A small YUV420 "lores" stream rides alongside the JPEG-encoded main stream; its Y plane is
        # the uncompressed luma the focus metric analyzes (no JPEG decode / quantization loss on
        # faint stars — CONCEPT §4). We grab it in a throttled post_callback rather than via
        # capture_array, so the focus path never contends with the encoder.
        config = self._picam2.create_video_configuration(
            main={"size": (self._w, self._h)},
            lores={"size": (self._lores_w, self._lores_h), "format": "YUV420"},
            # Configure the stream to *allow* the sensor's full exposure range, so star-preview /
            # long manual exposures aren't clamped to the default video frame duration. The manager
            # immediately applies the actual limits (fast for normal preview) after start.
            controls={"FrameDurationLimits": (8333, int(self.profile.exposure_us.max))},
        )
        self._picam2.configure(config)
        self._picam2.post_callback = self._grab_luma
        output = _BrokerOutput(self._emit)
        self._picam2.start_recording(JpegEncoder(), FileOutput(output), name="main")
        self._recording = True

    def _grab_luma(self, request) -> None:
        """Stash the lores Y plane, throttled — runs on picamera2's thread for every frame."""
        now = time.monotonic()
        if now - self._last_luma_t < 0.15:  # ~6 Hz is plenty for the focus meter
            return
        self._last_luma_t = now
        try:
            yuv = request.make_array("lores")  # YUV420: Y occupies the first `lores_h` rows
            self._latest_luma = np.ascontiguousarray(yuv[: self._lores_h, : self._lores_w])
        except Exception:  # noqa: BLE001 - a callback error must never disrupt streaming
            pass

    def _emit(self, frame: bytes) -> None:
        if self._loop is not None and self._broker is not None:
            self._loop.call_soon_threadsafe(self._broker.publish, frame)

    async def stop(self) -> None:
        await anyio.to_thread.run_sync(self._stop_sync)

    def _stop_sync(self) -> None:
        self._picam2.post_callback = None
        if self._recording:
            self._picam2.stop_recording()
            self._recording = False
        self._picam2.close()

    async def get_controls(self) -> dict:
        return dict(self._controls)

    async def set_controls(self, values: dict) -> None:
        # libcamera controls (e.g. ExposureTime in µs, AnalogueGain) apply live while recording.
        await anyio.to_thread.run_sync(self._picam2.set_controls, values)
        self._controls.update(values)

    def get_luma(self) -> np.ndarray | None:
        """The latest lores Y plane (stashed by the callback). None → manager decodes the JPEG."""
        return self._latest_luma

    def _full_crop(self) -> tuple[int, int, int, int]:
        """The sensor rectangle a normalized ROI is measured against (max ScalerCrop region)."""
        props = self._picam2.camera_properties
        maximum = props.get("ScalerCropMaximum")
        if maximum and maximum[2] and maximum[3]:
            return tuple(int(v) for v in maximum)  # type: ignore[return-value]
        w, h = props.get("PixelArraySize", (self._w, self._h))
        return (0, 0, int(w), int(h))

    async def set_zoom(self, roi: tuple[float, float, float, float] | None) -> None:
        await anyio.to_thread.run_sync(self._set_zoom_sync, roi)

    def _set_zoom_sync(self, roi: tuple[float, float, float, float] | None) -> None:
        x, y, full_w, full_h = self._full_crop()
        if roi is None:
            crop = (x, y, full_w, full_h)
        else:
            x0, y0, x1, y1 = roi
            cw = max(1, int((x1 - x0) * full_w))
            ch = max(1, int((y1 - y0) * full_h))
            crop = (x + int(x0 * full_w), y + int(y0 * full_h), cw, ch)
        self._picam2.set_controls({"ScalerCrop": crop})
        self._controls["ScalerCrop"] = crop

    async def capture_still(
        self, exposure_us: int, gain: float, raw: bool, ae: bool
    ) -> CaptureResult:
        return await anyio.to_thread.run_sync(self._capture_sync, exposure_us, gain, raw, ae)

    def _capture_sync(self, exposure_us: int, gain: float, raw: bool, ae: bool) -> CaptureResult:
        """Pause preview, switch to a full-res still config, capture, then restore preview.

        The single sensor can't stream preview and integrate a long exposure at once, so the preview
        is genuinely paused for the duration (CONCEPT §4). Runs on a worker thread — it blocks for
        roughly the exposure time. With ``ae`` on, the sensor meters the shot; otherwise the given
        exposure/gain are locked.
        """
        was_recording = self._recording
        if was_recording:
            self._picam2.stop_recording()
            self._recording = False
        self._picam2.post_callback = (
            None  # the still config has no lores stream; _start_sync re-arms
        )
        try:
            controls = (
                {"AeEnable": True}
                if ae
                else {
                    "ExposureTime": int(exposure_us),
                    "AnalogueGain": float(gain),
                    "AeEnable": False,
                }
            )
            still = self._picam2.create_still_configuration(
                raw={} if raw else None,
                controls=controls,
            )
            self._picam2.configure(still)
            self._picam2.start()
            request = self._picam2.capture_request()
            try:
                image = request.make_image("main").convert("RGB")
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=92)
                width, height = image.size
                raw_bytes = self._dng_bytes(request) if raw else None
            finally:
                request.release()
            self._picam2.stop()
        finally:
            if was_recording:
                self._start_sync()  # bring the preview stream back up
        return CaptureResult(
            jpeg=buf.getvalue(), width=width, height=height, raw=raw_bytes, raw_ext="dng"
        )

    @staticmethod
    def _dng_bytes(request) -> bytes:
        """Serialize the sensor raw as DNG. picamera2 writes to a path, so round-trip via a temp."""
        fd, name = tempfile.mkstemp(suffix=".dng")
        os.close(fd)
        try:
            request.save_dng(name)
            return Path(name).read_bytes()
        finally:
            os.unlink(name)
