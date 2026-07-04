"""High-level camera settings and their translation to libcamera controls.

The API speaks in these validated, sensor-agnostic settings; the manager clamps them to the
detected :class:`CameraProfile` and translates them into the low-level libcamera control dict that
both the mock and the picamera2 driver consume via ``set_controls``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal

from .profile import CameraProfile

PreviewMode = Literal["normal", "star"]

# Frame period for the responsive video preview (~30 fps ceiling).
_NORMAL_FRAME_US = (8_333, 33_333)
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


def merge(settings: CameraSettings, update: dict) -> CameraSettings:
    """Apply a partial update (only known keys) to the current settings."""
    allowed = {"ae_enable", "awb_enable", "exposure_us", "gain", "preview_mode"}
    clean = {k: v for k, v in update.items() if k in allowed and v is not None}
    return replace(settings, **clean)


def to_controls(settings: CameraSettings) -> dict:
    """Translate settings into a libcamera control dict for the driver."""
    controls: dict = {"AeEnable": settings.ae_enable, "AwbEnable": settings.awb_enable}
    if not settings.ae_enable:
        controls["ExposureTime"] = int(settings.exposure_us)
        controls["AnalogueGain"] = float(settings.gain)

    if settings.preview_mode == "star":
        # Long frame period so a multi-second exposure can actually complete each frame — this is
        # what makes stars visible in the preview at all (see CONCEPT §4).
        dur = int(settings.exposure_us) if not settings.ae_enable else _STAR_DEFAULT_US
        dur = max(dur, 500_000)
        controls["FrameDurationLimits"] = (dur, dur)
    elif not settings.ae_enable and settings.exposure_us > _NORMAL_FRAME_US[1]:
        # Normal mode, but a manual exposure longer than a video frame: raise the frame-duration
        # ceiling to fit it, otherwise libcamera silently clamps the exposure to ~33 ms.
        controls["FrameDurationLimits"] = (_NORMAL_FRAME_US[0], int(settings.exposure_us))
    else:
        controls["FrameDurationLimits"] = _NORMAL_FRAME_US

    return controls
