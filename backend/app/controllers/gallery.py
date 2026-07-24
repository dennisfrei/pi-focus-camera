"""Gallery: list captures, serve thumbnails / full images / raw, and delete.

Files live under the captures directory; the DB stores basenames, which we resolve here. Thumbnails
and full images are served inline (shown in the UI); raw frames are served as downloads.
"""

from __future__ import annotations

import contextlib

from litestar import Request, delete, get
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from litestar.response import File

from ..storage import captures


async def _record_or_404(manager, capture_id: int) -> dict:
    record = await captures.get_capture(manager.db_path, capture_id)
    if record is None:
        raise NotFoundException(detail=f"no capture #{capture_id}")
    return record


@get("/api/gallery")
async def list_gallery(request: Request) -> dict:
    manager = request.app.state.manager
    return {"captures": await captures.list_captures(manager.db_path)}


@get("/api/gallery/{capture_id:int}/thumb")
async def get_thumb(request: Request, capture_id: FromPath[int]) -> File:
    manager = request.app.state.manager
    record = await _record_or_404(manager, capture_id)
    return File(
        path=manager.captures_dir / record["thumb_path"],
        media_type="image/jpeg",
        content_disposition_type="inline",
    )


@get("/api/gallery/{capture_id:int}/image")
async def get_image(request: Request, capture_id: FromPath[int]) -> File:
    manager = request.app.state.manager
    record = await _record_or_404(manager, capture_id)
    return File(
        path=manager.captures_dir / record["jpeg_path"],
        filename=record["jpeg_path"],
        media_type="image/jpeg",
        content_disposition_type="inline",
    )


@get("/api/gallery/{capture_id:int}/raw")
async def get_raw(request: Request, capture_id: FromPath[int]) -> File:
    manager = request.app.state.manager
    record = await _record_or_404(manager, capture_id)
    if not record["raw_path"]:
        raise NotFoundException(detail=f"capture #{capture_id} has no raw")
    media = "image/x-adobe-dng" if record["raw_path"].endswith("dng") else "image/png"
    return File(
        path=manager.captures_dir / record["raw_path"],
        filename=record["raw_path"],
        media_type=media,
        content_disposition_type="attachment",
    )


@delete("/api/gallery/{capture_id:int}", status_code=200)
async def delete_capture(request: Request, capture_id: FromPath[int]) -> dict:
    manager = request.app.state.manager
    record = await captures.delete_capture(manager.db_path, capture_id)
    if record is None:
        raise NotFoundException(detail=f"no capture #{capture_id}")
    for key in ("jpeg_path", "raw_path", "thumb_path"):
        name = record.get(key)
        if name:
            with contextlib.suppress(FileNotFoundError):
                (manager.captures_dir / name).unlink()
    return {"deleted": capture_id}
