"""Shared fixtures: each test gets a fully isolated app on its own tmp SQLite DB + captures dir.

Before this, endpoint tests shared the dev ``astrocam.db`` (relative path from the global settings),
which let one test's presets/captures leak into another. The app factory (`create_app`) plus a
per-test `Settings` fixes that at the root.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar.testing import TestClient

from app.config import Settings
from app.main import create_app


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(
        db_path=tmp_path / "test.db",
        captures_dir=tmp_path / "captures",
        **overrides,
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """An isolated app + client (mock camera, tmp DB/captures)."""
    with TestClient(app=create_app(_settings(tmp_path))) as test_client:
        yield test_client


@pytest.fixture
def power_client(tmp_path: Path) -> Iterator[TestClient]:
    """Like ``client`` but with the shutdown/reboot power controls enabled."""
    settings = _settings(tmp_path, enable_power_controls=True)
    with TestClient(app=create_app(settings)) as test_client:
        yield test_client
