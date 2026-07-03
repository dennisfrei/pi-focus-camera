"""Sequence / intervalometer: capture N frames × exposure × interval, cancelable.

Progress is pushed over the ``/api/live`` WebSocket (``sequence`` state); each frame lands in the
gallery like a single capture.
"""

from __future__ import annotations

from litestar import Request, post
from litestar.exceptions import ClientException
from pydantic import BaseModel, Field


class SequenceRequest(BaseModel):
    count: int = Field(ge=1, le=999, description="Number of frames to capture.")
    interval_s: float = Field(default=0.0, ge=0.0, description="Delay between frames, seconds.")
    exposure_us: int | None = Field(
        default=None, ge=1, description="Per-frame exposure; defaults to the current setting."
    )
    raw: bool = False


@post("/api/sequence")
async def start_sequence(request: Request, data: SequenceRequest) -> dict:
    manager = request.app.state.manager
    try:
        return manager.start_sequence(
            count=data.count,
            interval_s=data.interval_s,
            exposure_us=data.exposure_us,
            raw=data.raw,
        )
    except RuntimeError as exc:
        raise ClientException(detail=str(exc)) from exc  # 400: already running


@post("/api/sequence/cancel")
async def cancel_sequence(request: Request) -> dict:
    manager = request.app.state.manager
    return {"cancelled": manager.cancel_sequence()}
