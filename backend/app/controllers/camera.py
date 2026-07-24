"""Camera controls: read the sensor profile and current settings, apply new ones.

Settings are the high-level, sensor-agnostic model (:class:`~app.camera.settings.CameraSettings`).
``PATCH`` accepts a partial update as a typed model — wrong types are rejected with 400 rather than
crashing, and only known keys reach the manager, which then clamps exposure/gain to the detected
:class:`~app.camera.profile.CameraProfile` before translating to libcamera controls.
"""

from __future__ import annotations

from typing import Literal

from litestar import Request, get, patch
from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    """A partial camera-settings update; every field is optional (only sent keys are applied)."""

    ae_enable: bool | None = None
    awb_enable: bool | None = None
    exposure_us: int | None = Field(default=None, ge=1)
    gain: float | None = Field(default=None, gt=0)
    preview_mode: Literal["normal", "star"] | None = None


@get("/api/camera/settings")
async def get_settings(request: Request) -> dict:
    manager = request.app.state.manager
    return {"profile": manager.profile.as_dict(), "settings": manager.settings.as_dict()}


@patch("/api/camera/settings")
async def update_settings(request: Request, data: SettingsUpdate) -> dict:
    manager = request.app.state.manager
    merged = await manager.apply_settings(data.model_dump(exclude_unset=True))
    return {"settings": merged.as_dict()}
