"""A hardware-free camera driver: renders a moving test pattern as JPEG.

Lets the whole app run and be developed on any machine. Draws a drifting "star" plus a crosshair
so the live view, focus overlays, and (later) focus metric have something plausible to react to.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import math
import time

import anyio
import numpy as np
from PIL import Image, ImageDraw

from .profile import CameraProfile, Control
from .stream import FrameBroker


class MockCamera:
    def __init__(self, width: int = 1280, height: int = 720, fps: int = 15) -> None:
        self._w = width
        self._h = height
        self._fps = fps
        self.profile = CameraProfile(
            model="MockCamera (test pattern)",
            resolution=(width, height),
            max_resolution=(width, height),
            # Fabricated to resemble an IMX219 (V2) so the UI has realistic bounds.
            exposure_us=Control(min=100.0, max=11_760_000.0, default=20_000.0),
            gain=Control(min=1.0, max=16.0, default=1.0),
            supports_raw=True,
            is_mock=True,
        )
        self._controls: dict = {"ExposureTime": 20_000, "AnalogueGain": 1.0}
        self._broker: FrameBroker | None = None
        self._task: asyncio.Task | None = None
        self._running = False

        # A fixed field of faint background stars (x, y in [0,1], peak brightness) so the histogram
        # has a realistic dark-sky shape with a high tail. Deterministic for reproducible dev.
        rng = np.random.default_rng(42)
        self._stars = [
            (float(x), float(y), int(b))
            for x, y, b in zip(
                rng.random(60), rng.random(60), rng.integers(120, 256, 60), strict=True
            )
        ]
        self._rng = np.random.default_rng(7)

    async def start(self, broker: FrameBroker) -> None:
        self._broker = broker
        self._running = True
        self._task = asyncio.create_task(self._produce())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def get_controls(self) -> dict:
        return dict(self._controls)

    async def set_controls(self, values: dict) -> None:
        self._controls.update(values)

    async def _produce(self) -> None:
        interval = 1.0 / self._fps
        t0 = time.monotonic()
        while self._running:
            t = time.monotonic() - t0
            jpeg = await anyio.to_thread.run_sync(self._render, t)
            if self._broker is not None:
                self._broker.publish(jpeg)
            await asyncio.sleep(interval)

    def _render(self, t: float) -> bytes:
        w, h = self._w, self._h

        # Faint sky background with per-frame shot noise → a realistic, gently shifting histogram.
        base = self._rng.normal(9.0, 3.0, size=(h, w)).clip(0, 255).astype(np.uint8)
        img = Image.fromarray(np.stack([base, base, base], axis=-1), mode="RGB")
        draw = ImageDraw.Draw(img)

        # Fixed background star field (gives the histogram its high-value tail).
        for sx, sy, br in self._stars:
            x, y = int(sx * w), int(sy * h)
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(br, br, br))

        # Drifting bright "star" with a soft glow — moves so the stream is visibly live.
        cx = int((0.5 + 0.30 * math.sin(t * 0.7)) * w)
        cy = int((0.5 + 0.30 * math.cos(t * 0.5)) * h)
        for radius, value in ((16, 40), (10, 90), (6, 170), (3, 255)):
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=(value, value, value),
            )

        # Faint crosshair for focus framing.
        draw.line([(w // 2, 0), (w // 2, h)], fill=(60, 0, 0), width=1)
        draw.line([(0, h // 2), (w, h // 2)], fill=(60, 0, 0), width=1)

        exp = self._controls.get("ExposureTime", 0)
        gain = self._controls.get("AnalogueGain", 1.0)
        draw.text(
            (12, 12), f"MockCamera  t={t:5.1f}s  exp={exp}us  gain={gain}", fill=(255, 80, 80)
        )

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
