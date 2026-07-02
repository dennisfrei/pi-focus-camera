"""Camera controls: read the sensor profile and current values, apply new ones.

M0 exposes read + a permissive set (the mock just stores them). Validation against the profile
and presets arrive in M3.
"""

from __future__ import annotations

from typing import Any

from litestar import Request, get, patch


@get("/api/camera/settings")
async def get_settings(request: Request) -> dict:
    manager = request.app.state.manager
    return {"profile": manager.profile.as_dict(), "controls": await manager.get_controls()}


@patch("/api/camera/settings")
async def update_settings(request: Request, data: dict[str, Any]) -> dict:
    manager = request.app.state.manager
    await manager.set_controls(data)
    return {"controls": await manager.get_controls()}
