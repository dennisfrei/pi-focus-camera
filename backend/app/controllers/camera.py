"""Camera controls: read the sensor profile and current settings, apply new ones.

Settings are the high-level, sensor-agnostic model (:class:`~app.camera.settings.CameraSettings`).
``PATCH`` accepts a partial update; the manager validates it against the detected
:class:`~app.camera.profile.CameraProfile` (clamping exposure/gain, dropping unknown keys) before
translating it into libcamera controls — no raw dict ever reaches the driver.
"""

from __future__ import annotations

from typing import Any

from litestar import Request, get, patch


@get("/api/camera/settings")
async def get_settings(request: Request) -> dict:
    manager = request.app.state.manager
    return {"profile": manager.profile.as_dict(), "settings": manager.settings.as_dict()}


@patch("/api/camera/settings")
async def update_settings(request: Request, data: dict[str, Any]) -> dict:
    manager = request.app.state.manager
    merged = await manager.apply_settings(data)
    return {"settings": merged.as_dict()}
