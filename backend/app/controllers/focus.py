"""Focus-assist controls: the ROI the metric is measured over, the metric mode, and 1:1 zoom."""

from __future__ import annotations

from typing import Literal

from litestar import Request, get, post
from pydantic import BaseModel, Field


class RoiUpdate(BaseModel):
    """Normalized region of interest, or ``roi=null`` to analyze the whole frame."""

    roi: tuple[float, float, float, float] | None = Field(
        default=None,
        description="(x0, y0, x1, y1) in [0, 1]; null clears the ROI (full frame).",
    )


class ModeUpdate(BaseModel):
    """Which focus metric to compute: scene (Laplacian) or star (HFD)."""

    mode: Literal["scene", "star"]


@get("/api/focus")
async def get_focus(request: Request) -> dict:
    manager = request.app.state.manager
    return {
        "roi": list(manager.focus_roi) if manager.focus_roi else None,
        "mode": manager.focus_mode,
        **manager.metrics,
    }


@post("/api/focus/roi")
async def set_focus_roi(request: Request, data: RoiUpdate) -> dict:
    manager = request.app.state.manager
    roi = tuple(data.roi) if data.roi else None
    manager.set_focus_roi(roi)
    return {"roi": list(roi) if roi else None}


@post("/api/focus/mode")
async def set_focus_mode(request: Request, data: ModeUpdate) -> dict:
    manager = request.app.state.manager
    return {"mode": manager.set_focus_mode(data.mode)}


@post("/api/focus/zoom")
async def set_focus_zoom(request: Request, data: RoiUpdate) -> dict:
    """Crop the sensor to the ROI for a true 1:1 zoom (hardware only; the mock zooms in CSS)."""
    manager = request.app.state.manager
    roi = tuple(data.roi) if data.roi else None
    await manager.set_zoom(roi)
    return {"roi": list(roi) if roi else None, "hw_zoom": manager.camera.supports_hw_zoom}
