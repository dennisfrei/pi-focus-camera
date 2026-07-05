"""Capture: take a still (optionally raw), stored to the gallery.

Long exposures report progress over the ``/api/live`` WebSocket (``capture`` state); this endpoint
returns once the capture is saved, with its gallery record.
"""

from __future__ import annotations

from typing import Literal

from litestar import Request, post
from pydantic import BaseModel, Field

FrameType = Literal["light", "dark", "flat", "bias"]


class CaptureRequest(BaseModel):
    raw: bool = False  # also save the sensor raw (DNG on the Pi, PNG stand-in on the mock)
    exposure_us: int | None = Field(
        default=None,
        ge=1,
        description="Exposure in microseconds; defaults to the current manual exposure setting.",
    )
    frame_type: FrameType = "light"  # light / dark / flat / bias — recorded for the stacking pipeline


@post("/api/capture")
async def capture(request: Request, data: CaptureRequest) -> dict:
    manager = request.app.state.manager
    record = await manager.capture(
        raw=data.raw, exposure_us=data.exposure_us, frame_type=data.frame_type
    )
    return record if record is not None else {"cancelled": True}


@post("/api/capture/cancel")
async def cancel_capture(request: Request) -> dict:
    manager = request.app.state.manager
    return {"cancelled": manager.cancel_capture()}
