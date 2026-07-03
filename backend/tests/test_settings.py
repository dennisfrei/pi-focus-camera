"""M3 camera-settings tests: validation model + the PATCH endpoint, against the mock."""

from __future__ import annotations

from litestar.testing import TestClient

from app.camera import settings as camsettings
from app.camera.profile import CameraProfile, Control
from app.camera.settings import CameraSettings
from app.main import app

PROFILE = CameraProfile(
    model="test",
    resolution=(1280, 720),
    max_resolution=(3280, 2464),
    exposure_us=Control(min=100.0, max=1_000_000.0, default=20_000.0),
    gain=Control(min=1.0, max=16.0, default=1.0),
    supports_raw=True,
)


def test_clamp_bounds_exposure_and_gain() -> None:
    over = CameraSettings(exposure_us=9_000_000, gain=99.0)
    clamped = camsettings.clamp(over, PROFILE)
    assert clamped.exposure_us == 1_000_000
    assert clamped.gain == 16.0

    under = CameraSettings(exposure_us=1, gain=0.0)
    clamped = camsettings.clamp(under, PROFILE)
    assert clamped.exposure_us == 100
    assert clamped.gain == 1.0


def test_merge_ignores_unknown_and_none_keys() -> None:
    base = CameraSettings()
    merged = camsettings.merge(base, {"gain": 4.0, "bogus": 1, "exposure_us": None})
    assert merged.gain == 4.0
    assert merged.exposure_us == base.exposure_us  # None ignored
    assert not hasattr(merged, "bogus")


def test_to_controls_manual_mode_sends_exposure_and_gain() -> None:
    manual = CameraSettings(ae_enable=False, exposure_us=500_000, gain=8.0)
    controls = camsettings.to_controls(manual)
    assert controls["AeEnable"] is False
    assert controls["ExposureTime"] == 500_000
    assert controls["AnalogueGain"] == 8.0


def test_to_controls_auto_mode_omits_manual_exposure() -> None:
    controls = camsettings.to_controls(CameraSettings(ae_enable=True))
    assert controls["AeEnable"] is True
    assert "ExposureTime" not in controls
    assert "AnalogueGain" not in controls


def test_to_controls_star_mode_uses_long_frame_duration() -> None:
    star = CameraSettings(preview_mode="star", ae_enable=False, exposure_us=2_000_000)
    controls = camsettings.to_controls(star)
    lo, hi = controls["FrameDurationLimits"]
    assert lo == hi == 2_000_000  # matches the requested exposure

    # Normal mode caps the frame period at video rates.
    normal = camsettings.to_controls(CameraSettings(preview_mode="normal"))
    assert normal["FrameDurationLimits"][1] <= 33_333


def test_star_mode_has_a_floor_even_on_auto() -> None:
    controls = camsettings.to_controls(CameraSettings(preview_mode="star", ae_enable=True))
    assert controls["FrameDurationLimits"][0] >= 500_000


def test_patch_endpoint_clamps_and_persists() -> None:
    with TestClient(app=app) as client:
        # Out-of-range gain is clamped to the mock's 16x ceiling, unknown keys dropped.
        resp = client.patch("/api/camera/settings", json={"gain": 999.0, "nope": 1})
        body = resp.json()["settings"]
        assert body["gain"] == 16.0
        # A follow-up GET returns the same clamped value.
        assert client.get("/api/camera/settings").json()["settings"]["gain"] == 16.0


def test_patch_star_mode_switch() -> None:
    with TestClient(app=app) as client:
        resp = client.patch("/api/camera/settings", json={"preview_mode": "star"})
        assert resp.json()["settings"]["preview_mode"] == "star"
