"""Focus-assist controls: set the region of interest the sharpness metric is computed over."""

from __future__ import annotations

from litestar import Request, get, post
from pydantic import BaseModel, Field


class RoiUpdate(BaseModel):
    """Normalized region of interest, or ``roi=null`` to analyze the whole frame."""

    roi: tuple[float, float, float, float] | None = Field(
        default=None,
        description="(x0, y0, x1, y1) in [0, 1]; null clears the ROI (full frame).",
    )


@get("/api/focus")
async def get_focus(request: Request) -> dict:
    manager = request.app.state.manager
    return {"roi": list(manager.focus_roi) if manager.focus_roi else None, **manager.metrics}


@post("/api/focus/roi")
async def set_focus_roi(request: Request, data: RoiUpdate) -> dict:
    manager = request.app.state.manager
    roi = tuple(data.roi) if data.roi else None
    manager.set_focus_roi(roi)
    return {"roi": list(roi) if roi else None}
