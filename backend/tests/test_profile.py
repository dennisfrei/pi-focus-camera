"""Profile detection tests — exercise build_profile against a fake picamera2 (no hardware)."""

from __future__ import annotations

from app.camera.manager import select_camera
from app.camera.profile import build_profile
from app.config import settings


class FakeImx219:
    """Mimics the picamera2 attributes we read, with IMX219 (Camera Module V2) values."""

    camera_controls = {
        "ExposureTime": (75, 11_766_018, 20_000),
        "AnalogueGain": (1.0, 16.0, None),  # libcamera may report None for the default
    }
    camera_properties = {"Model": "imx219", "PixelArraySize": (3280, 2464)}
    sensor_modes = [{"bit_depth": 10}]


def test_build_profile_reads_sensor_limits() -> None:
    profile = build_profile(FakeImx219(), (1280, 720))
    assert profile.model == "imx219"
    assert profile.is_mock is False
    assert profile.resolution == (1280, 720)
    assert profile.max_resolution == (3280, 2464)
    assert profile.exposure_us.max == 11_766_018  # ~11.8 s, the V2 ceiling
    assert profile.supports_raw is True


def test_build_profile_handles_none_default() -> None:
    # Gain default is None -> midpoint of (1.0, 16.0).
    profile = build_profile(FakeImx219(), (1280, 720))
    assert profile.gain.default == (1.0 + 16.0) / 2


def test_build_profile_falls_back_when_control_missing() -> None:
    class NoControls:
        camera_controls: dict = {}
        camera_properties: dict = {}
        sensor_modes: list = []

    profile = build_profile(NoControls(), (640, 480))
    assert profile.exposure_us.max > 0  # fallback used
    assert profile.max_resolution == (640, 480)  # falls back to preview resolution
    assert profile.supports_raw is False


def test_select_camera_falls_back_to_mock_without_hardware() -> None:
    # On the dev box picamera2 isn't importable, so we must get the mock.
    camera = select_camera(settings)
    assert camera.profile.is_mock is True
