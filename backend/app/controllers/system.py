"""Health and system info."""

from __future__ import annotations

from litestar import Request, get


@get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@get("/api/system")
async def system_info(request: Request) -> dict:
    manager = request.app.state.manager
    return {
        "camera": manager.profile.model,
        "mock": manager.profile.is_mock,
        "state": "preview" if manager.started else "idle",
        "profile": manager.profile.as_dict(),
    }
