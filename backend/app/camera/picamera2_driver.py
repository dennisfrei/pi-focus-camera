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

import anyio
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

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

    async def start(self, broker: FrameBroker) -> None:
        self._broker = broker
        self._loop = asyncio.get_running_loop()
        await anyio.to_thread.run_sync(self._start_sync)

    def _start_sync(self) -> None:
        config = self._picam2.create_video_configuration(main={"size": (self._w, self._h)})
        self._picam2.configure(config)
        output = _BrokerOutput(self._emit)
        self._picam2.start_recording(JpegEncoder(), FileOutput(output))
        self._recording = True

    def _emit(self, frame: bytes) -> None:
        if self._loop is not None and self._broker is not None:
            self._loop.call_soon_threadsafe(self._broker.publish, frame)

    async def stop(self) -> None:
        await anyio.to_thread.run_sync(self._stop_sync)

    def _stop_sync(self) -> None:
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
