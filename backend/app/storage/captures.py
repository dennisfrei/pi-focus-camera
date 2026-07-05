"""Capture metadata (SQLite) and on-disk files for the gallery.

Each capture is a row plus a small set of files under the captures directory: a display JPEG, a
thumbnail, and — when raw was requested — the raw frame (DNG on the Pi, PNG stand-in on the mock).
Only basenames are stored in the DB so the captures directory can be moved (e.g. onto a USB stick).
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from PIL import Image

from ..camera.base import CaptureResult

THUMB_WIDTH = 320


async def init_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS captures ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " created REAL NOT NULL,"
            " settings TEXT NOT NULL,"
            " width INTEGER NOT NULL,"
            " height INTEGER NOT NULL,"
            " jpeg_path TEXT NOT NULL,"
            " raw_path TEXT,"
            " thumb_path TEXT NOT NULL)"
        )
        await db.commit()


def _row_to_dict(row: aiosqlite.Row) -> dict:
    return {
        "id": row["id"],
        "created": row["created"],
        "settings": json.loads(row["settings"]),
        "width": row["width"],
        "height": row["height"],
        "jpeg_path": row["jpeg_path"],
        "raw_path": row["raw_path"],
        "thumb_path": row["thumb_path"],
        "has_raw": row["raw_path"] is not None,
    }


def write_files(captures_dir: Path, result: CaptureResult, settings: dict) -> dict:
    """Write the JPEG, thumbnail and optional raw to disk; return the row to insert.

    Runs in a worker thread (Pillow is blocking). Returns basenames only — see module docstring.
    """
    captures_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
    # Prefix with the frame type (light/dark/flat/bias) so files sort by kind for stacking.
    frame_type = str(settings.get("frame_type", "light"))
    base = f"{frame_type}_{stamp}"

    jpeg_name = f"{base}.jpg"
    (captures_dir / jpeg_name).write_bytes(result.jpeg)

    thumb = Image.open(io.BytesIO(result.jpeg))
    thumb.thumbnail((THUMB_WIDTH, THUMB_WIDTH))
    thumb_name = f"{base}_thumb.jpg"
    thumb.convert("RGB").save(captures_dir / thumb_name, format="JPEG", quality=80)

    raw_name = None
    if result.raw is not None:
        raw_name = f"{base}.{result.raw_ext}"
        (captures_dir / raw_name).write_bytes(result.raw)

    return {
        "created": time.time(),
        "settings": json.dumps(settings),
        "width": result.width,
        "height": result.height,
        "jpeg_path": jpeg_name,
        "raw_path": raw_name,
        "thumb_path": thumb_name,
    }


async def add_capture(path: Path, row: dict) -> int:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "INSERT INTO captures"
            " (created, settings, width, height, jpeg_path, raw_path, thumb_path)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                row["created"],
                row["settings"],
                row["width"],
                row["height"],
                row["jpeg_path"],
                row["raw_path"],
                row["thumb_path"],
            ),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_captures(path: Path) -> list[dict]:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM captures ORDER BY created DESC")
        return [_row_to_dict(r) for r in await cur.fetchall()]


async def get_capture(path: Path, capture_id: int) -> dict | None:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,))
        row = await cur.fetchone()
    return _row_to_dict(row) if row else None


async def delete_capture(path: Path, capture_id: int) -> dict | None:
    """Delete the row and return it (with file basenames) so the caller can unlink the files."""
    record = await get_capture(path, capture_id)
    if record is None:
        return None
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
        await db.commit()
    return record
