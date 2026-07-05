"""The camera driver contract.

Both :class:`~app.camera.mock.MockCamera` and (later) ``Picamera2Camera`` implement this
protocol. Application code never touches a concrete driver directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .profile import CameraProfile
from .stream import FrameBroker

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class CaptureResult:
    """One captured still: a display JPEG plus, optionally, the raw frame.

    ``raw_ext`` names the raw format so storage picks the right extension — ``dng`` on the Pi,
    ``png`` as the mock's lossless stand-in (there's no real sensor raw to emit off-device).
    """

    jpeg: bytes
    width: int
    height: int
    raw: bytes | None = None
    raw_ext: str = "dng"


@runtime_checkable
class Camera(Protocol):
    # Sensor capabilities, including ``supports_hw_zoom`` (true 1:1 ScalerCrop vs the mock's CSS
    # zoom) — the single source of truth read by both the manager and the frontend.
    profile: CameraProfile

    async def start(self, broker: FrameBroker) -> None:
        """Begin producing preview JPEG frames into ``broker``."""
        ...

    async def stop(self) -> None:
        """Stop producing frames and release the sensor."""
        ...

    async def get_controls(self) -> dict:
        """Return current control values (e.g. ExposureTime, AnalogueGain)."""
        ...

    async def set_controls(self, values: dict) -> None:
        """Apply control values; unknown/out-of-range keys are the driver's concern."""
        ...

    def get_luma(self) -> np.ndarray | None:
        """Latest preview luma as a 2D uint8 array, or None if unavailable (analyze the JPEG)."""
        ...

    async def set_zoom(self, roi: tuple[float, float, float, float] | None) -> None:
        """Crop the sensor to ``roi`` (normalized) for a 1:1 zoom, or None to restore full frame."""
        ...

    async def capture_still(
        self, exposure_us: int, gain: float, raw: bool, ae: bool
    ) -> CaptureResult:
        """Capture a full-resolution still, then restore preview.

        When ``ae`` is True the sensor meters the exposure itself (``exposure_us``/``gain`` are
        ignored); when False they are applied as a locked manual exposure.
        """
        ...
