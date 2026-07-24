"""Litestar application entrypoint.

Owns the camera lifecycle (via lifespan), wires up the API routes, and serves the built Svelte
SPA as static files. In development the SPA is served by Vite instead (proxying ``/api`` here),
so an empty ``static/`` directory is fine.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from litestar import Litestar
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.static_files import create_static_files_router

from . import __version__
from .camera.manager import CameraManager
from .config import Settings, settings
from .controllers.camera import get_settings, update_settings
from .controllers.capture import cancel_capture, capture
from .controllers.focus import get_focus, set_focus_mode, set_focus_roi, set_focus_zoom
from .controllers.gallery import (
    delete_capture,
    get_image,
    get_raw,
    get_thumb,
    list_gallery,
)
from .controllers.live_ws import live
from .controllers.presets import apply_preset, delete_preset, list_presets, save_preset
from .controllers.sequence import cancel_sequence, start_sequence
from .controllers.stream import stream
from .controllers.system import health, power, system_info
from .storage import captures, presets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).parent / "static"
VENDOR_DIR = Path(__file__).parent / "vendor"

# Swagger UI, served from vendored assets under /vendor/swagger so the docs work fully offline
# on the Pi (no CDN). Interactive docs at /api/docs, raw schema at /api/docs/openapi.json.
openapi_config = OpenAPIConfig(
    title="Prime Focus Camera API",
    version=__version__,
    description="Live preview streaming, camera control, and capture for a prime-focus astro camera.",
    path="/api/docs",
    render_plugins=[
        SwaggerRenderPlugin(
            js_url="/vendor/swagger/swagger-ui-bundle.js",
            css_url="/vendor/swagger/swagger-ui.css",
            standalone_preset_js_url="/vendor/swagger/swagger-ui-standalone-preset.js",
            # Suppress the default CDN favicon so the page makes no external requests.
            favicon="<link rel='icon' href='data:,'>",
        )
    ],
)


ROUTE_HANDLERS = [
    stream,
    live,
    health,
    system_info,
    power,
    get_settings,
    update_settings,
    list_presets,
    save_preset,
    apply_preset,
    delete_preset,
    get_focus,
    set_focus_roi,
    set_focus_mode,
    set_focus_zoom,
    capture,
    cancel_capture,
    start_sequence,
    cancel_sequence,
    list_gallery,
    get_thumb,
    get_image,
    get_raw,
    delete_capture,
]


def create_app(app_settings: Settings | None = None) -> Litestar:
    """Build a Litestar app bound to ``app_settings`` (defaults to the env-driven singleton).

    The factory lets each instance own its own config, camera manager, and SQLite database — so
    tests spin up a fully isolated app on a tmp DB instead of sharing global on-disk state.
    """
    cfg = app_settings or settings
    STATIC_DIR.mkdir(exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: Litestar) -> AsyncIterator[None]:
        await presets.init_db(cfg.db_path)
        await captures.init_db(cfg.db_path)
        manager = CameraManager(cfg)
        await manager.start()
        app.state.settings = cfg
        app.state.manager = manager
        try:
            yield
        finally:
            await manager.stop()

    return Litestar(
        route_handlers=[
            *ROUTE_HANDLERS,
            # Vendored Swagger UI assets (offline docs).
            create_static_files_router(path="/vendor", directories=[VENDOR_DIR]),
            # Serves the built SPA at "/"; API routes above take precedence.
            create_static_files_router(path="/", directories=[STATIC_DIR], html_mode=True),
        ],
        openapi_config=openapi_config,
        lifespan=[lifespan],
    )


# The default app for uvicorn / `poe serve` (app.main:app), bound to the env-driven settings.
app = create_app()
