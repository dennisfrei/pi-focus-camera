"""High-level camera settings and their translation to libcamera controls.

The API speaks in these validated, sensor-agnostic settings; the manager clamps them to the
detected :class:`CameraProfile` and translates them into the low-level libcamera control dict that
both the mock and the picamera2 driver consume via ``set_controls``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from typing import Literal

from .profile import CameraProfile

PreviewMode = Literal["normal", "star"]

# Frame period for the video preview: 15–30 fps. Capping the framerate (vs the old 120 fps ceiling)
# roughly halves the software JPEG encoder's work — a Pi 4 running the encoder 24/7 was throttling at
# 80 °C, and 15–30 fps is plenty for focusing/framing.
_NORMAL_FRAME_US = (33_333, 66_666)
# Default long frame period for star preview when exposure is on auto.
_STAR_DEFAULT_US = 1_000_000


@dataclass(frozen=True)
class CameraSettings:
    ae_enable: bool = True  # auto-exposure; when False, ExposureTime/gain are applied manually
    awb_enable: bool = True  # auto white balance
    exposure_us: int = 20_000
    gain: float = 1.0
    preview_mode: PreviewMode = "normal"

    def as_dict(self) -> dict:
        return asdict(self)


def clamp(settings: CameraSettings, profile: CameraProfile) -> CameraSettings:
    """Clamp exposure/gain into the sensor's real limits."""
    exp = int(min(max(settings.exposure_us, profile.exposure_us.min), profile.exposure_us.max))
    gain = float(min(max(settings.gain, profile.gain.min), profile.gain.max))
    return replace(settings, exposure_us=exp, gain=gain)


_FIELD_NAMES = frozenset(f.name for f in fields(CameraSettings))


def merge(settings: CameraSettings, update: dict) -> CameraSettings:
    """Apply a partial update to the current settings (only known dataclass fields; skips None)."""
    clean = {k: v for k, v in update.items() if k in _FIELD_NAMES and v is not None}
    return replace(settings, **clean)


def to_controls(settings: CameraSettings) -> dict:
    """Translate settings into a libcamera control dict for the driver."""
    controls: dict = {"AeEnable": settings.ae_enable, "AwbEnable": settings.awb_enable}
    if not settings.ae_enable:
        controls["ExposureTime"] = int(settings.exposure_us)
        controls["AnalogueGain"] = float(settings.gain)

    if settings.preview_mode == "star":
        # Star preview integrates long frames so faint stars are visible — the stream necessarily
        # crawls (CONCEPT §4). This is the *only* mode that slows the live preview.
        dur = int(settings.exposure_us) if not settings.ae_enable else _STAR_DEFAULT_US
        dur = max(dur, 500_000)
        controls["FrameDurationLimits"] = (dur, dur)
    else:
        # Normal mode always runs at video rate for a responsive framing preview — even with a long
        # manual exposure set. That exposure applies to *captures* (which use their own still
        # config); libcamera just clamps the preview's ExposureTime to the video frame duration.
        controls["FrameDurationLimits"] = _NORMAL_FRAME_US

    return controls
