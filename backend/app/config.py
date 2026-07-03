"""Runtime configuration (env-driven, prefix ``PFC_``)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PFC_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080

    # Force the mock camera even if picamera2 is importable (useful for dev on the Pi).
    force_mock: bool = False

    captures_dir: Path = Path("captures")
    db_path: Path = Path("astrocam.db")

    # Preview stream resolution for the real camera (picamera2).
    preview_width: int = 1280
    preview_height: int = 720

    # How often to recompute focus/histogram metrics (Hz).
    focus_hz: float = 5.0

    # Mock camera characteristics (dev only).
    mock_width: int = 1280
    mock_height: int = 720
    mock_fps: int = 15


settings = Settings()
