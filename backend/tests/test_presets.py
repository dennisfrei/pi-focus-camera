"""M3 preset tests: the SQLite storage layer (tmp db) and the REST endpoints (mock camera)."""

from __future__ import annotations

from pathlib import Path

from litestar.testing import TestClient

from app.storage import presets


async def test_preset_storage_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "presets.db"
    await presets.init_db(db)

    assert await presets.list_presets(db) == []

    await presets.save_preset(db, "Moon", {"gain": 2.0, "exposure_us": 5000})
    await presets.save_preset(db, "M42", {"gain": 8.0, "exposure_us": 2_000_000})

    names = [p["name"] for p in await presets.list_presets(db)]
    assert names == ["M42", "Moon"]  # ordered by name

    assert (await presets.get_preset(db, "Moon"))["gain"] == 2.0
    assert await presets.get_preset(db, "missing") is None

    # Overwrite in place (INSERT OR REPLACE), not a duplicate row.
    await presets.save_preset(db, "Moon", {"gain": 3.0})
    assert (await presets.get_preset(db, "Moon"))["gain"] == 3.0
    assert len(await presets.list_presets(db)) == 2

    assert await presets.delete_preset(db, "Moon") is True
    assert await presets.delete_preset(db, "Moon") is False
    assert [p["name"] for p in await presets.list_presets(db)] == ["M42"]


def test_preset_endpoints_save_apply_delete(client: TestClient) -> None:
    name = "Moon"
    # Set a distinctive gain, then snapshot it as a preset.
    client.patch("/api/camera/settings", json={"gain": 6.0})
    saved = client.post("/api/camera/presets", json={"name": name}).json()["presets"]
    assert [p["name"] for p in saved] == [name]

    # Change the live setting, then apply the preset to restore it.
    client.patch("/api/camera/settings", json={"gain": 1.0})
    applied = client.post(f"/api/camera/presets/{name}/apply").json()["settings"]
    assert applied["gain"] == 6.0

    # Applying a missing preset is a 404.
    assert client.post("/api/camera/presets/does-not-exist/apply").status_code == 404

    # Delete removes it.
    resp = client.delete(f"/api/camera/presets/{name}")
    assert resp.status_code == 200
    assert resp.json()["presets"] == []


def test_save_preset_requires_a_name(client: TestClient) -> None:
    assert client.post("/api/camera/presets", json={"name": "  "}).status_code == 400


def test_save_preset_rejects_slash_names(client: TestClient) -> None:
    """A '/' can't round-trip the path param, so it must be rejected rather than orphaned."""
    assert client.post("/api/camera/presets", json={"name": "a/b"}).status_code == 400
    assert client.post("/api/camera/presets", json={"name": "a\\b"}).status_code == 400
    assert client.get("/api/camera/presets").json()["presets"] == []  # nothing orphaned
