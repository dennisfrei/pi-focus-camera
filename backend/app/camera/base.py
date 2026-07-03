"""The camera driver contract.

Both :class:`~app.camera.mock.MockCamera` and (later) ``Picamera2Camera`` implement this
protocol. Application code never touches a concrete driver directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .profile import CameraProfile
from .stream import FrameBroker

if TYPE_CHECKING:
    import numpy as np


@runtime_checkable
class Camera(Protocol):
    profile: CameraProfile
    # True when the driver can crop the sensor for a true 1:1 zoom (ScalerCrop); the mock can't and
    # the UI falls back to a CSS zoom of the downscaled preview.
    supports_hw_zoom: bool

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
