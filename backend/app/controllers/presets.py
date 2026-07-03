"""Named setting presets: save/apply/delete bundles of camera settings.

A preset is a snapshot of the current :class:`~app.camera.settings.CameraSettings` (e.g. "Moon",
"Star focus"), persisted in SQLite so it survives a restart. Applying one runs it back through the
manager's validation, so a preset saved on one sensor still clamps sanely on another.
"""

from __future__ import annotations

from typing import Any

from litestar import Request, delete, get, post
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath

from ..storage import presets


@get("/api/camera/presets")
async def list_presets(request: Request) -> dict:
    manager = request.app.state.manager
    return {"presets": await presets.list_presets(manager.db_path)}


@post("/api/camera/presets")
async def save_preset(request: Request, data: dict[str, Any]) -> dict:
    """Save the current settings under ``name`` (overwrites an existing preset of that name)."""
    manager = request.app.state.manager
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValidationException(detail="preset name is required")
    await presets.save_preset(manager.db_path, name, manager.settings.as_dict())
    return {"presets": await presets.list_presets(manager.db_path)}


@post("/api/camera/presets/{name:str}/apply")
async def apply_preset(request: Request, name: FromPath[str]) -> dict:
    """Load a preset and apply it through the manager (validated against the current sensor)."""
    manager = request.app.state.manager
    stored = await presets.get_preset(manager.db_path, name)
    if stored is None:
        raise NotFoundException(detail=f"no preset named {name!r}")
    merged = await manager.apply_settings(stored)
    return {"settings": merged.as_dict()}


@delete("/api/camera/presets/{name:str}", status_code=200)
async def delete_preset(request: Request, name: FromPath[str]) -> dict:
    manager = request.app.state.manager
    removed = await presets.delete_preset(manager.db_path, name)
    if not removed:
        raise NotFoundException(detail=f"no preset named {name!r}")
    return {"presets": await presets.list_presets(manager.db_path)}
