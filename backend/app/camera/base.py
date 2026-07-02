"""The camera driver contract.

Both :class:`~app.camera.mock.MockCamera` and (later) ``Picamera2Camera`` implement this
protocol. Application code never touches a concrete driver directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .profile import CameraProfile
from .stream import FrameBroker


@runtime_checkable
class Camera(Protocol):
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
