"""Named camera-setting presets, stored in SQLite.

Each preset is a snapshot of :class:`~app.camera.settings.CameraSettings` (e.g. "Moon",
"Star focus"). Connections are opened per operation — trivial load, and it keeps the module free of
lifecycle state.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import aiosqlite


async def init_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS presets ("
            " name TEXT PRIMARY KEY,"
            " settings TEXT NOT NULL,"
            " created REAL NOT NULL)"
        )
        await db.commit()


async def list_presets(path: Path) -> list[dict]:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT name, settings FROM presets ORDER BY name")
        rows = await cur.fetchall()
    return [{"name": r["name"], "settings": json.loads(r["settings"])} for r in rows]


async def get_preset(path: Path, name: str) -> dict | None:
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT settings FROM presets WHERE name = ?", (name,))
        row = await cur.fetchone()
    return json.loads(row["settings"]) if row else None


async def save_preset(path: Path, name: str, settings: dict) -> None:
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO presets (name, settings, created) VALUES (?, ?, ?)",
            (name, json.dumps(settings), time.time()),
        )
        await db.commit()


async def delete_preset(path: Path, name: str) -> bool:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("DELETE FROM presets WHERE name = ?", (name,))
        await db.commit()
    return cur.rowcount > 0
