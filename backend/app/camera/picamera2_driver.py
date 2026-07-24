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
import contextlib
import io
import logging
import os
import tempfile
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


def _ensure_dng_compat() -> None:
    """Make pidng's DNG camera class tolerate the extra positional arg picamera2 passes.

    On Raspberry Pi OS the apt ``picamera2`` calls ``Picamera2Camera(config, metadata, model)`` but
    no released ``pidng`` accepts that third ``model`` arg — its ``__init__`` is ``(config,
    metadata)`` — so ``request.save_dng`` dies with *"takes 3 positional arguments but 4 were
    given"*. Chasing pidng versions doesn't help. Instead, wrap the class's ``__init__`` to keep only
    the positional args it actually declares (the extra ``model`` is a cosmetic DNG tag), so raw DNG
    export works regardless of the installed pidng. Idempotent; a no-op on any version that already
    accepts the arg (or ``*args``).
    """
    import importlib
    import inspect

    cls = None
    for modname in ("picamera2.request", "pidng.camdefs", "pidng.core"):
        try:
            cls = getattr(importlib.import_module(modname), "Picamera2Camera", None)
        except Exception:  # noqa: BLE001 - probing optional module paths
            cls = None
        if cls is not None:
            break
    if cls is None:
        logger.warning("pidng DNG-compat shim: Picamera2Camera not found — DNG may fail")
        return

    orig = cls.__init__
    if getattr(orig, "_pfc_patched", False):
        return
    try:
        params = list(inspect.signature(orig).parameters.values())
    except (ValueError, TypeError):
        return  # no introspectable signature (C impl) — can't safely shim
    if any(p.kind == p.VAR_POSITIONAL for p in params):
        return  # already accepts *args — nothing to fix
    keep = sum(1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)) - 1
    accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in params)
    allowed_kw = {p.name for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}

    def _init(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        # Drop the extra positional/keyword `model` the newer picamera2 passes (cosmetic DNG tag).
        kw = kwargs if accepts_kwargs else {k: v for k, v in kwargs.items() if k in allowed_kw}
        orig(self, *args[:keep], **kw)

    _init._pfc_patched = True  # type: ignore[attr-defined]
    cls.__init__ = _init
    logger.info("Applied pidng DNG compatibility shim (drops the extra picamera2 model arg)")


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
        # Frame-duration range the video config is built to allow (default = fast normal preview).
        # The manager widens this via set_frame_duration_envelope when entering star preview.
        self._fd_envelope: tuple[int, int] = (33_333, 66_666)

    async def start(self, broker: FrameBroker) -> None:
        self._broker = broker
        self._loop = asyncio.get_running_loop()
        await anyio.to_thread.run_sync(self._start_sync)

    async def set_frame_duration_envelope(self, lo_us: int, hi_us: int) -> None:
        envelope = (int(lo_us), int(hi_us))
        if envelope == self._fd_envelope:
            return
        self._fd_envelope = envelope
        if self._recording:
            # Reconfigure the running stream so the new frame-duration range is actually permitted.
            await anyio.to_thread.run_sync(self._reconfigure_sync)

    def _reconfigure_sync(self) -> None:
        self._picam2.stop_recording()
        self._recording = False
        self._start_sync()

    def _start_sync(self) -> None:
        # Single main stream, JPEG-encoded by the hardware-friendly recording path (the official
        # picamera2 MJPEG recipe). Focus analyzes the decoded main JPEG (via the manager's fallback),
        # so there's no second stream / capture to contend with the encoder and stall the preview.
        # FrameDurationLimits sets the range this video config allows; the manager reconfigures it
        # (fast for normal, wide up to the sensor max for star) so long star exposures aren't clamped.
        config = self._picam2.create_video_configuration(
            main={"size": (self._w, self._h)},
            controls={"FrameDurationLimits": self._fd_envelope},
        )
        self._picam2.configure(config)
        output = _BrokerOutput(self._emit)
        self._picam2.start_recording(JpegEncoder(), FileOutput(output), name="main")
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

    def get_luma(self) -> np.ndarray | None:
        """No dedicated luma stream — return None so the manager decodes the preview JPEG instead."""
        return None

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
        started = False
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
            started = True
            request = self._picam2.capture_request()
            try:
                image = request.make_image("main").convert("RGB")
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=92)
                width, height = image.size
                raw_bytes = None
                if raw:
                    # Best-effort: a DNG failure (e.g. a picamera2/pidng version skew) must not lose
                    # the JPEG or wedge the camera — save what we have and log why.
                    try:
                        raw_bytes = self._dng_bytes(request)
                    except Exception:
                        logger.exception(
                            "DNG save failed — saved JPEG only. The driver already shims the known "
                            "picamera2/pidng arg-count skew; if this persists it's a different fault."
                        )
            finally:
                request.release()
        finally:
            # Always stop before restoring the preview — configuring a running camera raises
            # "Camera must be stopped before configuring".
            if started:
                with contextlib.suppress(Exception):
                    self._picam2.stop()
            if was_recording:
                self._start_sync()  # bring the preview stream back up
        return CaptureResult(
            jpeg=buf.getvalue(), width=width, height=height, raw=raw_bytes, raw_ext="dng"
        )

    @staticmethod
    def _dng_bytes(request) -> bytes:
        """Serialize the sensor raw as DNG. picamera2 writes to a path, so round-trip via a temp."""
        _ensure_dng_compat()  # tolerate the picamera2/pidng arg-count skew (idempotent)
        fd, name = tempfile.mkstemp(suffix=".dng")
        os.close(fd)
        try:
            request.save_dng(name)
            return Path(name).read_bytes()
        finally:
            os.unlink(name)
