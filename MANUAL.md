# Manual — Setup, Configuration & Deployment

Operator's guide for the Prime Focus Camera: running it on a dev machine, configuring it, and
deploying it to the Raspberry Pi. For **using the app at the telescope** (what each control does),
open the **? Help** button in the app itself — that guide ships with the UI. Architecture and
design rationale live in [CONCEPT.md](CONCEPT.md); the build plan in
[IMPLEMENTATION.md](IMPLEMENTATION.md).

---

## 1. Local development setup (no camera needed)

Everything develops on any Linux/macOS machine against the **mock camera** — a synthetic star
field that honors exposure/gain/star-preview controls, so the full UI is exercisable without
hardware.

### Prerequisites

| Tool | Version | Used for |
|------|---------|----------|
| [uv](https://docs.astral.sh/uv/) | any recent | Python interpreter + deps (`uv.lock` committed) |
| Node.js + npm | ≥ 20 | Frontend build/dev only — **not needed at runtime** |
| git | any | — |

Python itself is managed by uv (`backend/.python-version` pins 3.14; the code floor is 3.13).

### Backend

```bash
cd backend
uv sync                 # creates .venv with the pinned Python + locked deps
uv run poe dev          # Litestar with reload on 0.0.0.0:8080
```

Poe tasks (defined in `backend/pyproject.toml`):

| Task | What it does |
|------|--------------|
| `uv run poe dev` | dev server with auto-reload, port 8080 |
| `uv run poe serve` | production server (no reload) |
| `uv run poe test` | pytest (53 tests, all mock-driven — no hardware needed) |
| `uv run poe lint` | ruff check |
| `uv run poe format` | ruff format |

The Pi camera stack (`picamera2` etc.) is deliberately **not** in `pyproject.toml` — it doesn't
resolve on a dev box. It's the optional **`pi` extra** in `pyproject.toml` (deploy Path A,
`uv sync --extra pi`) or comes from apt (Path B); see §4.

**CI** (`.github/workflows/ci.yml`) runs ruff + the pytest suite on **Python 3.13** (the deployment
floor) and svelte-check + the frontend build on every push/PR — so a 3.14-only construct fails in CI
rather than on the Pi.

### Frontend

```bash
cd frontend
npm install
npm run dev             # Vite on 0.0.0.0:5173, proxies /api (incl. WebSocket) to :8080
```

Open the printed URL — you should see the moving test pattern, a live focus score, and the
histogram. `npm run check` runs svelte-check + tsc; `npm run build` produces the production bundle.

### Dev loop notes

- Two terminals: `poe dev` + `npm run dev`. Vite handles hot reload; the proxy targets
  `http://localhost:8080` (`frontend/vite.config.ts`).
- Both servers bind `0.0.0.0`, so a phone on the same LAN can open either (use the machine's IP).
- **API docs**: Swagger UI at `http://localhost:8080/api/docs` (schema at
  `/api/docs/openapi.json`). The assets are vendored in `backend/app/vendor/` — no CDN, works
  offline.
- The backend logs which driver it picked at startup:
  `Falling back to MockCamera (No module named 'picamera2')` is the expected line on a dev box.

### Production build (single process)

```bash
cd frontend && npm run build      # bundles straight into backend/app/static/
cd ../backend && uv run poe serve # Litestar serves SPA + API on :8080 — no Node at runtime
```

`npm run build` **empties** `backend/app/static/` first (Vite `emptyOutDir`), so don't put
hand-made files there.

---

## 2. Configuration

All backend settings are environment variables with the **`PFC_`** prefix, loaded from the
environment or a **`backend/.env`** file (template: [`backend/.env.example`](backend/.env.example)).
Everything has a sensible default — a bare checkout runs with zero config.

| Variable | Default | Meaning |
|----------|---------|---------|
| `PFC_HOST` | `0.0.0.0` | Bind address |
| `PFC_PORT` | `8080` | Bind port |
| `PFC_FORCE_MOCK` | `false` | Use the mock camera even if `picamera2` imports — useful for demos/dev on a Pi |
| `PFC_ENABLE_POWER_CONTROLS` | `false` | Show the in-app **Shut down / Reboot** buttons and honor them. Off by default so a dev box can't be powered off by mistake; `install.sh` sets it and adds the sudoers rule on the Pi |
| `PFC_CAPTURES_DIR` | `captures` | Where captured JPEG/raw/thumbnails are written (relative to the backend working dir). **Point at a USB drive for real sessions** — raw files are large |
| `PFC_DB_PATH` | `astrocam.db` | SQLite file holding presets + capture metadata. The DB stores only file *basenames*, so the captures dir can be relocated |
| `PFC_PREVIEW_WIDTH` / `PFC_PREVIEW_HEIGHT` | `1280` / `720` | Preview stream resolution for the real camera |
| `PFC_FOCUS_HZ` | `5.0` | How often the focus metric/histogram recompute. Lower it if a Pi struggles |
| `PFC_MOCK_WIDTH` / `PFC_MOCK_HEIGHT` / `PFC_MOCK_FPS` | `1280` / `720` / `15` | Mock camera geometry/cadence (dev only) |

Runtime data written by the app (all gitignored): `astrocam.db`, `captures/`.

There is **no auth** by design — v1 assumes the Pi's own isolated access point
(CONCEPT.md §9). Do not expose the port to an untrusted network.

---

## 3. What's where (repo map)

```
backend/
  app/
    camera/        # drivers (mock + picamera2), manager, focus metrics, settings model
    controllers/   # REST + WebSocket endpoints
    storage/       # SQLite (presets, captures)
    static/        # ← built SPA lands here (generated, gitignored)
    vendor/        # self-hosted Swagger UI assets
  tests/           # pytest, all runnable without hardware
  .env.example     # configuration template
frontend/          # Svelte 5 + Vite SPA (PWA: manifest + service worker in public/)
deploy/            # install.sh, setup-ap.sh, setup-mdns.sh, astrocam.service
src/               # OLD 2020 prototype — retired after M1 hardware verification, ignore
```

---

## 4. Deployment on the Raspberry Pi

Target: Raspberry Pi 4/5, Raspberry Pi OS **Bookworm/Trixie** (libcamera stack, NetworkManager),
camera module attached (V2/HQ/Module 3 — capabilities are detected at runtime).

### 4.0 Before anything: verify the camera

```bash
rpicam-hello --list-cameras
```

If this doesn't list your sensor, fix the ribbon cable / enable the camera first — nothing in this
app can work without it.

### 4.1 The picamera2 question (Path A vs Path B)

`picamera2` binds to the OS's libcamera and is the one dependency that can't be treated normally
(CONCEPT.md §7):

- **Path A — pip stack, keeps uv's Python 3.14:**
  ```bash
  sudo apt install -y libcap-dev        # picamera2 → python-prctl needs the libcap headers
  cd backend && uv sync --extra pi      # installs picamera2 + rpi-libcamera + rpi-kms
  ```
  The Pi stack is the optional **`pi` extra** in `pyproject.toml`, so a plain `uv sync` never
  touches it. Clean *if* wheels exist for your Python/libcamera combo; `rpi-libcamera` is
  version-sensitive. Try this if you want to stay on 3.14.
- **Path B — apt package on the system Python (what `install.sh` does; most reliable):**
  ```bash
  sudo apt install -y python3-picamera2 python3-libcamera
  cd backend
  uv venv --system-site-packages --python /usr/bin/python3   # venv that can see apt packages
  uv pip install -e .                                        # litestar, uvicorn, numpy, ...
  ```
  This pins only the **on-device** interpreter (3.13 on Trixie); dev stays on 3.14. The code's
  floor is `requires-python >=3.13` and ruff lints to `py313`, so nothing 3.14-only sneaks in.

### 4.2 One-shot provisioning

```bash
git clone <this repo> ~/pi-focus-camera
cd ~/pi-focus-camera
bash deploy/install.sh
```

`install.sh` does, in order:

1. `apt install python3-picamera2 python3-libcamera avahi-daemon`
2. Backend venv via **Path B** + `uv pip install -e .`
3. Frontend `npm ci && npm run build` → `backend/app/static/` (skipped with a warning if npm is
   missing — build elsewhere and copy `frontend/dist/` content into `backend/app/static/`)
4. mDNS: enables avahi and sets the hostname to `astrocam` → **http://astrocam.local:8080**
5. systemd: templates `deploy/astrocam.service` with your user + checkout path, enables and
   starts it

It deliberately does **not** create the WiFi access point — that would cut the connection you're
installing over.

### 4.3 The access point

When you're ready (from a **local console/keyboard or wired session** — this drops WiFi):

```bash
AP_SSID=AstroCam AP_PASS='choose-8+chars' sudo -E bash deploy/setup-ap.sh
```

NetworkManager's shared mode gives DHCP+DNS automatically; the Pi is **10.42.0.1** and the hotspot
autoconnects on boot (priority above saved networks). Join the `AstroCam` WiFi on the phone and
open **http://astrocam.local:8080** (or `http://10.42.0.1:8080`). To undo:
`nmcli connection delete Hotspot` and reconnect to your WiFi.

Environment overrides: `AP_SSID`, `AP_PASS` (min 8 chars), `AP_IFACE` (default `wlan0`).

### 4.4 Operating the service

```bash
systemctl status astrocam        # is it running?
journalctl -u astrocam -f        # live logs (driver selection, captures, errors)
sudo systemctl restart astrocam  # after config changes
```

Configuration for the service: put a `.env` next to `backend/pyproject.toml` (the unit's
`WorkingDirectory` is `backend/`), e.g. `PFC_CAPTURES_DIR=/mnt/usb/captures`, then restart.

The system panel's **Shut down / Reboot** buttons (enabled on the Pi via
`PFC_ENABLE_POWER_CONTROLS`, with a sudoers rule `install.sh` installs) let you power the camera
down cleanly from the phone instead of pulling the plug — do this before disconnecting power to
avoid SD-card corruption.

### 4.5 Updating

```bash
cd ~/pi-focus-camera
git pull
cd frontend && npm ci && npm run build
sudo systemctl restart astrocam
```

(Re-run `uv pip install -e .` in `backend/` only if Python dependencies changed.)

### 4.6 Install the app on the phone

With the page open in the phone browser, use "Add to Home Screen" — the PWA manifest + service
worker make it a standalone, offline-capable app. Note the service worker caches the app shell:
after an update, the **first** load may serve the previous version; reload once to pick up the new
build.

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| UI shows **MOCK CAMERA** badge on the Pi | `picamera2` not importable in the venv (check `journalctl -u astrocam` for the fallback log line), no camera detected (`rpicam-hello --list-cameras`), or `PFC_FORCE_MOCK=true` left set |
| No live view, "no stream" placeholder | Backend not running / wrong port. `systemctl status astrocam`; in dev, is `poe dev` up and the Vite proxy pointing at it? |
| "reconnecting…" link status | WebSocket can't connect — same causes as above; also triggered briefly by a backend restart (it auto-reconnects) |
| Stream frozen during a capture | Expected — one sensor can't stream and integrate a long exposure at once. The capture bar shows the countdown; preview resumes after |
| Stars invisible in preview at night | Normal-mode preview is ~33 ms/frame. Switch to **Star** preview and lock AE off with raised gain (see in-app Help) |
| Focus number frozen / "no star in the region" | The ROI contains no star bright enough to measure — drag the box over a brighter star or raise gain |
| Stale UI after deploying an update | PWA shell cache — reload the page once (or clear site data) |
| `astrocam.local` not resolving | avahi not running (`systemctl status avahi-daemon`) or the client OS lacks mDNS — use `http://10.42.0.1:8080` on the AP |
| Disk filling up | Raw files are big. Set `PFC_CAPTURES_DIR` to a USB drive; the system panel shows free space |
| Dev box: `uv sync` tries to build picamera2 | It shouldn't — the Pi stack isn't in `pyproject.toml`. You ran `uv pip install -r requirements-pi.txt` on a dev box; recreate the venv (`rm -rf .venv && uv sync`) |

## 6. Known issues

The 2026-07-04 code review found 10 issues; **all are fixed** (with regression tests) — see
[IMPLEMENTATION.md § Known issues](IMPLEMENTATION.md#known-issues--code-review-2026-07-04) for the
record. Several fixes touch hardware-only paths (post-capture settings restore, long manual
exposures in normal preview, 1:1 zoom vs. focus ROI, auto-exposure captures) and are locked in by
mock tests but only fully *observable* on the Pi — confirm them during the first hardware session.
