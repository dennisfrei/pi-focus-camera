"""Sensor capability model.

Built once at startup — from the mock's fabricated values, or (on the Pi) from
``picam2.camera_controls`` — and handed to the frontend so its controls adapt to whatever
sensor is attached (V2 today, HQ / Module 3 later) with no code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Control:
    """A numeric camera control's detected range."""

    min: float
    max: float
    default: float


@dataclass(frozen=True)
class CameraProfile:
    model: str
    resolution: tuple[int, int]
    max_resolution: tuple[int, int]
    exposure_us: Control
    gain: Control
    supports_raw: bool
    is_mock: bool = False
    supports_hw_zoom: bool = False  # true 1:1 sensor crop (ScalerCrop) vs the mock's CSS zoom

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "resolution": list(self.resolution),
            "max_resolution": list(self.max_resolution),
            "exposure_us": vars(self.exposure_us),
            "gain": vars(self.gain),
            "supports_raw": self.supports_raw,
            "is_mock": self.is_mock,
            "supports_hw_zoom": self.supports_hw_zoom,
        }


class _Picamera2Like(Protocol):
    """The slice of the picamera2 API we read to build a profile (kept hardware-free/testable)."""

    camera_controls: dict[str, tuple[Any, Any, Any]]
    camera_properties: dict[str, Any]
    sensor_modes: list[Any]


def _control(raw: dict[str, tuple[Any, Any, Any]], name: str, fallback: Control) -> Control:
    """Read a (min, max, default) tuple from picamera2's camera_controls, tolerating gaps.

    libcamera sometimes reports ``None`` for a control's default; fall back to the midpoint.
    """
    if name not in raw:
        return fallback
    lo, hi, default = raw[name]
    lo = float(lo) if lo is not None else fallback.min
    hi = float(hi) if hi is not None else fallback.max
    default = float(default) if default is not None else (lo + hi) / 2
    return Control(min=lo, max=hi, default=default)


def build_profile(picam2: _Picamera2Like, resolution: tuple[int, int]) -> CameraProfile:
    """Derive a :class:`CameraProfile` from a live picamera2 instance.

    This is how the *same app* adapts to V2 / HQ / Module 3: exposure and gain limits come from
    the sensor itself (e.g. IMX219 ≈ 11.8 s max, IMX477 ≈ 200 s) rather than being hardcoded.
    """
    controls = picam2.camera_controls
    props = picam2.camera_properties

    exposure = _control(controls, "ExposureTime", Control(100.0, 11_760_000.0, 20_000.0))
    gain = _control(controls, "AnalogueGain", Control(1.0, 16.0, 1.0))

    model = str(props.get("Model", "Raspberry Pi Camera"))
    pixel_array = props.get("PixelArraySize")
    max_resolution = tuple(pixel_array) if pixel_array else resolution

    return CameraProfile(
        model=model,
        resolution=resolution,
        max_resolution=max_resolution,  # type: ignore[arg-type]
        exposure_us=exposure,
        gain=gain,
        supports_raw=bool(getattr(picam2, "sensor_modes", None)),
        is_mock=False,
        supports_hw_zoom=True,  # libcamera ScalerCrop gives a real sensor-pixel zoom
    )
