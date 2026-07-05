#!/usr/bin/env bash
#
# One-shot provisioning for the Prime Focus Camera on a Raspberry Pi (Bookworm/Trixie).
#
# Installs the camera stack, builds the backend venv and the frontend, and installs the systemd
# service + mDNS. It deliberately does NOT bring up the WiFi access point (that would disconnect the
# Pi mid-install) — run deploy/setup-ap.sh yourself from a local/wired session when ready.
#
# Uses deploy "Path B" from CONCEPT.md §7: apt's python3-picamera2 on the system Python, with a
# uv venv that can see those apt site-packages. It's the most reliable combo; Path A (pip
# picamera2 + rpi-libcamera on uv's Python 3.14) is the alternative if you prefer to stay on 3.14.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

echo "==> Installing on $APP_DIR as user $RUN_USER"

echo "==> apt: camera stack + avahi"
sudo apt-get update -y
sudo apt-get install -y python3-picamera2 python3-libcamera avahi-daemon

if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' not found. Install it first: https://docs.astral.sh/uv/getting-started/install/" >&2
  exit 1
fi

echo "==> Backend venv (Path B: system-site-packages so it sees apt's picamera2)"
cd "$APP_DIR/backend"
uv venv --system-site-packages --python /usr/bin/python3
# Install the exact locked versions (uv.lock) rather than a fresh resolve, then the project itself.
# --no-hashes keeps it working across architectures (the Pi pulls its own aarch64 wheels).
REQ="$(mktemp)"
uv export --no-dev --no-emit-project --frozen --no-hashes -o "$REQ"
uv pip install -r "$REQ"
uv pip install -e . --no-deps
rm -f "$REQ"

echo "==> Frontend build"
if command -v npm >/dev/null 2>&1; then
  cd "$APP_DIR/frontend"
  npm ci
  npm run build   # outputs into backend/app/static/
else
  echo "   npm not found — skipping frontend build. Build it elsewhere and copy dist/ into"
  echo "   backend/app/static/, or install nodejs and re-run."
fi

echo "==> Allowing the service user to power off / reboot (for the in-app buttons)"
SUDOERS=/etc/sudoers.d/astrocam-power
printf '%s ALL=(root) NOPASSWD: /sbin/shutdown, /usr/sbin/shutdown, /sbin/reboot, /usr/sbin/reboot\n' \
  "$RUN_USER" | sudo tee "$SUDOERS" >/dev/null
sudo chmod 440 "$SUDOERS"

echo "==> mDNS (astrocam.local)"
bash "$APP_DIR/deploy/setup-mdns.sh"

echo "==> systemd service"
UNIT=/etc/systemd/system/astrocam.service
sed -e "s#__USER__#$RUN_USER#g" -e "s#__APP_DIR__#$APP_DIR#g" \
  "$APP_DIR/deploy/astrocam.service" | sudo tee "$UNIT" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now astrocam.service

echo
echo "==> Done. The app is running on http://astrocam.local:8080 (and the Pi's current IP)."
echo "    To make the Pi its own access point, from a local session run:"
echo "        AP_SSID=AstroCam AP_PASS='choose-8+chars' sudo -E bash $APP_DIR/deploy/setup-ap.sh"
echo "    Then join that WiFi on the phone and open http://astrocam.local:8080"
