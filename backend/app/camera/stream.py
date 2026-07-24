"""MJPEG frame broker: one producer, many subscribers.

The driver publishes the latest JPEG; each connected client subscribes and receives frames as
they arrive (dropping missed frames is fine for a live preview). ``publish`` must run on the
event loop thread. A threaded producer (the real picamera2 encoder callback) should hand frames
over with ``loop.call_soon_threadsafe(broker.publish, jpeg)``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class FrameBroker:
    def __init__(self) -> None:
        self._frame: bytes | None = None
        self._event = asyncio.Event()

    @property
    def latest(self) -> bytes | None:
        return self._frame

    def publish(self, frame: bytes) -> None:
        """Store the newest frame and wake all subscribers. Event-loop thread only."""
        self._frame = frame
        # Pulse: release current waiters, then reset so the next frame wakes them again.
        self._event.set()
        self._event.clear()

    async def subscribe(self) -> AsyncIterator[bytes]:
        """Yield frames as they are published. Emits the current frame immediately if present."""
        last: bytes | None = None
        if self._frame is not None:
            last = self._frame
            yield last
        while True:
            await self._event.wait()
            frame = self._frame
            if frame is not None and frame is not last:
                last = frame
                yield frame
