"""Live preview as an MJPEG multipart stream."""

from __future__ import annotations

from collections.abc import AsyncIterator

from litestar import Request, get
from litestar.response import Stream

BOUNDARY = "frame"


@get("/api/stream.mjpg")
async def stream(request: Request) -> Stream:
    manager = request.app.state.manager

    async def generate() -> AsyncIterator[bytes]:
        async for frame in manager.broker.subscribe():
            yield (
                b"--" + BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
            )

    return Stream(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={"Cache-Control": "no-cache, private", "Pragma": "no-cache"},
    )
