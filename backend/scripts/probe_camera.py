"""Print the detected camera profile as JSON.

Run this ON THE PI (with the camera stack installed) to verify M1 without the web app:

    cd backend
    uv run python scripts/probe_camera.py        # Path A (uv + picamera2)
    # or, Path B (apt picamera2 on system python):
    python scripts/probe_camera.py

Exits non-zero with a clear message if picamera2 is missing or no camera is attached.
"""

from __future__ import annotations

import json
import sys

try:
    from picamera2 import Picamera2
except ImportError:
    sys.exit(
        "picamera2 not importable — install the Pi camera stack first "
        "(see backend/requirements-pi.txt / CONCEPT.md §7). This script only runs on the Pi."
    )

from app.camera.profile import build_profile


def main() -> None:
    try:
        picam2 = Picamera2()
    except Exception as exc:  # noqa: BLE001 - report any libcamera/hardware error plainly
        sys.exit(f"Could not open the camera: {exc}\nCheck `rpicam-hello --list-cameras`.")

    try:
        profile = build_profile(picam2, (1280, 720))
        print(json.dumps(profile.as_dict(), indent=2))
        print(
            f"\nMax exposure: {profile.exposure_us.max / 1_000_000:.1f} s   "
            f"Gain: {profile.gain.min}–{profile.gain.max}   Raw: {profile.supports_raw}",
            file=sys.stderr,
        )
    finally:
        picam2.close()


if __name__ == "__main__":
    main()
