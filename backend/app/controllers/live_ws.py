"""Live telemetry over WebSocket.

Pushes camera state plus focus-assist metrics (sharpness score, histogram, clipping) at the
configured focus rate so the meter tracks the focuser responsively. Capture progress is added in M4.

The handler pushes from a child task while the main coroutine blocks on ``receive()``. That way it
notices a client disconnect immediately and tears the push loop down — instead of spinning forever
against a phone that walked away.
"""

from __future__ import annotations

import asyncio
import contextlib

from litestar import WebSocket, websocket
from litestar.exceptions import WebSocketDisconnect


@websocket("/api/live")
async def live(socket: WebSocket) -> None:
    await socket.accept()
    manager = socket.app.state.manager
    interval = 1.0 / max(manager.focus_hz, 1)

    async def push() -> None:
        while True:
            metrics = manager.metrics
            await socket.send_json(
                {
                    "state": "preview" if manager.started else "idle",
                    "camera": manager.profile.model,
                    "mock": manager.profile.is_mock,
                    "focus_score": metrics.get("focus_score", 0.0),
                    "focus_mode": metrics.get("focus_mode", manager.focus_mode),
                    "focus_metric": metrics.get("focus_metric", ""),
                    "focus_direction": metrics.get("focus_direction", "higher"),
                    "hfd": metrics.get("hfd"),
                    "peak": metrics.get("peak"),
                    "star_found": metrics.get("star_found"),
                    "histogram": metrics.get("histogram", []),
                    "clipping": metrics.get("clipping", 0.0),
                    "roi": metrics.get("roi"),
                    "settings": manager.settings.as_dict(),
                    "capture": manager.capture_state,
                    "sequence": manager.sequence_state,
                }
            )
            await asyncio.sleep(interval)

    push_task = asyncio.create_task(push())
    try:
        # Blocks until the client sends something or disconnects.
        await socket.receive()
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await push_task
