"""Health and system info: camera, plus real CPU temp / disk / uptime where available.

The readings come from Linux sysfs/procfs and ``shutil``; on a non-Pi dev box the ones that don't
exist return ``None`` rather than failing, so the panel degrades gracefully. AP SSID/client count is
deferred to M7 (the access point isn't set up until then).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from litestar import Request, get, post
from litestar.exceptions import PermissionDeniedException
from pydantic import BaseModel

from ..config import settings


def cpu_temp_c() -> float | None:
    try:
        milli = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return round(int(milli) / 1000, 1)
    except (OSError, ValueError):
        return None


def uptime_s() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def disk_usage(path: Path) -> dict:
    """Free space where captures are written (its parent if the dir doesn't exist yet, else root)."""
    for candidate in (path, path.parent, Path("/")):
        try:
            total, used, free = shutil.disk_usage(candidate)
            return {"total": total, "used": used, "free": free}
        except OSError:
            continue
    return {"total": 0, "used": 0, "free": 0}


@get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@get("/api/system")
async def system_info(request: Request) -> dict:
    manager = request.app.state.manager
    return {
        "camera": manager.profile.model,
        "mock": manager.profile.is_mock,
        "state": "preview" if manager.started else "idle",
        "profile": manager.profile.as_dict(),
        "cpu_temp_c": cpu_temp_c(),
        "uptime_s": uptime_s(),
        "disk": disk_usage(manager.captures_dir),
        "power_controls": settings.enable_power_controls,
    }


class PowerRequest(BaseModel):
    action: Literal["shutdown", "reboot"]


# Fire-and-forget so the response returns before the host goes down. `sudo -n` needs the sudoers
# rule install.sh adds; without it the command fails and the host stays up.
_POWER_COMMANDS = {
    "shutdown": ["sudo", "-n", "shutdown", "-h", "now"],
    "reboot": ["sudo", "-n", "reboot"],
}


@post("/api/system/power")
async def power(request: Request, data: PowerRequest) -> dict:
    if not settings.enable_power_controls:
        raise PermissionDeniedException(
            detail="power controls are disabled (PFC_ENABLE_POWER_CONTROLS)"
        )
    subprocess.Popen(_POWER_COMMANDS[data.action])  # noqa: S603 - fixed command, validated action
    return {"action": data.action}
