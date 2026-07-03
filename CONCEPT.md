# Prime Focus Camera — Concept & Architecture

> Turn a Raspberry Pi + camera module into a prime-focus astro camera for a telescope.
> The Pi runs everything, is its own WiFi access point, and a phone/tablet connects
> to a local web GUI to **focus**, **adjust camera settings**, and **capture** images —
> entirely offline.

---

## 1. Target setup (decided)

| Aspect        | Decision                                                                 |
|---------------|--------------------------------------------------------------------------|
| Hardware      | **Raspberry Pi 4/5**, Camera Module **V2 (IMX219)** now, upgradeable to **HQ (IMX477)** / **Module 3 (IMX708)** |
| OS            | Raspberry Pi OS **Bookworm / Trixie** (libcamera stack, NetworkManager)  |
| Camera lib    | **picamera2** (libcamera) — *not* the dead legacy `picamera`; behind a driver interface |
| Backend       | **Python 3.14 + Litestar** (ASGI), served by uvicorn/granian             |
| Tooling       | **uv** for Python (deps, venv, `.python-version` = 3.14)                 |
| Frontend      | **Svelte 5 + Vite**, built to static files (Node is build-time only)     |
| Networking    | Pi as **WiFi access point** via NetworkManager; phone joins & opens GUI  |
| Scope         | **Focus + Capture** — live view w/ focus assist *and* stills incl. long exposure / raw |

The design abstracts over the sensor so the **same app works on V2 today and HQ/Module 3 later** —
capabilities (max exposure, raw support, resolutions) are *detected at runtime*, not hardcoded.

> **Honest scope for the V2 sensor.** The IMX219 (1.12 µm pixels, tiny area, ~11.8 s max exposure,
> no cooling) is a *focus aid + lunar/planetary* camera, not a deep-sky camera. This app is fully
> useful with it for focusing, Moon, planets, and bright-target snapshots. The deep-sky capture
> pipeline (long-exposure DNG subs for stacking) is designed in from the start but only becomes
> genuinely productive with the **HQ (IMX477)** upgrade. Planetary "lucky imaging" (high-fps raw
> video bursts) is a possible future mode — see §9.

> **Dev vs. device.** This repo is developed on a machine **without** a camera; the target Pi is
> separate. So the camera is a **pluggable driver** (`MockCamera` for dev, `Picamera2Camera` on the
> Pi) and picamera2 is an **optional dependency group** — see §7 for the uv + Python 3.14 caveat.

---

## 2. What the old repo has vs. what's missing

The existing `src/` is a 2020-era prototype. Almost all of it must be rebuilt.

### Broken / obsolete
- `picamera` — **dead** on modern OS. libcamera replaced the legacy stack; the tool is now `rpicam-*`. → use **picamera2**.
- `Flask 1.1` + `flask-restplus 0.13` — both **abandoned**. → **Litestar**.
- `api.py` references an undefined `video_capture` — never ran.
- `test.py` loads `axios` from **unpkg.com (CDN)** — silently fails with no internet. → self-host everything.
- README mentions an **ELM frontend** that was never built. → Svelte.

### Missing entirely (the real work)
1. **Modern camera pipeline** (picamera2): preview stream + still capture from one sensor.
2. **Astro capture**: manual exposure/gain, long exposure, **raw DNG** for stacking, capture sequences.
3. **Focus assist** — the whole point of a *focus* camera (sharpness metric, digital zoom, peaking).
4. **Single-sensor concurrency** — you cannot stream preview *and* run a 10 s exposure at once; needs a coordinated camera manager with mode-switching.
5. **Capture storage** — save, thumbnail, browse gallery, download to phone.
6. **WiFi access point** + **mDNS** (`astrocam.local`) + **autostart** (systemd).
7. **Offline PWA** GUI, mobile-first, with an astronomy **red night-vision theme**.
8. **Runtime capability detection** so V2/HQ/Module 3 all "just work".

---

## 3. Sensor capabilities (why detection matters)

| Sensor | Board | Max exposure | Native res | Raw | Notes |
|--------|-------|--------------|-----------|-----|-------|
| IMX219 | Camera Module **V2** | **~11.8 s** | 3280×2464 | DNG | Fine for Moon/planets & focus; weak for deep-sky |
| IMX477 | **HQ Camera** | **~200 s** | 4056×3040 | DNG | Best astro option; C/CS mount suits telescopes |
| IMX708 | **Module 3** | **~112 s** | 4608×2592 | DNG | Autofocus irrelevant at prime focus; HDR |

picamera2 exposes real limits via `picam2.camera_controls['ExposureTime']` → `(min, max, default)`.
The backend reads these at startup, builds a **`CameraProfile`**, and the frontend renders its
exposure slider/limits from that profile. Upgrading the sensor needs **zero code changes**.

---

## 4. Architecture

```
┌────────────────────────── Raspberry Pi (offline, AP) ──────────────────────────┐
│                                                                                 │
│   Camera Module ──libcamera──►  ┌──────────────────────────────┐                │
│                                 │      CameraManager            │  (singleton,   │
│                                 │  - picamera2 instance         │   async-locked)│
│                                 │  - preview stream (MJPEG)     │                │
│                                 │  - still/long-exp capture     │                │
│                                 │  - focus metric + histogram   │                │
│                                 │  - CameraProfile (detected)   │                │
│                                 └───────┬───────────┬───────────┘                │
│                                         │           │                            │
│                    frame broker (MJPEG) │           │ state/metrics              │
│                                         ▼           ▼                            │
│                         ┌──────────────────────────────────────┐                │
│                         │            Litestar (ASGI)            │                │
│                         │  GET  /api/stream.mjpg   (multipart)  │                │
│                         │  WS   /api/live          (state,hist) │                │
│                         │  REST /api/camera/settings            │                │
│                         │  REST /api/capture       (+ progress) │                │
│                         │  REST /api/gallery/*      (list/dl)   │                │
│                         │  REST /api/system         (temp,disk) │                │
│                         │  GET  /*  → static Svelte SPA         │                │
│                         └──────────────────┬───────────────────┘                │
│         SQLite (capture metadata, presets) │  captures/ (JPG/DNG on disk)        │
│                                            │                                     │
│   NetworkManager  (WiFi AP 10.42.0.1)  +  avahi (astrocam.local)  +  systemd     │
└─────────────────────────────────────────────┼──────────────────────────────────┘
                                               │  WiFi
                                        ┌──────▼───────┐
                                        │   Phone /    │  Svelte PWA in browser
                                        │   Tablet     │  live view · controls · gallery
                                        └──────────────┘
```

### Why this split
- **MJPEG multipart** for the video → dead-simple, works in every mobile browser, no plugins, robust offline. (WebRTC is faster but far too heavy/fragile to justify on a LAN of one.)
- **WebSocket** for live telemetry (focus score, histogram, exposure readout, capture progress, camera state) → push, not poll; keeps the MJPEG stream just pixels.
- **REST** for commands (set exposure, capture, delete) → easy to reason about, cache-safe.

### The hard part: one sensor, two jobs
There is a single physical sensor. The `CameraManager` owns it behind an **async lock**:

- **Idle/preview mode**: continuous low-res MJPEG (e.g. 640×480 or 1280×720) at video framerate; computes focus metric + histogram per N frames.
- **Capture mode**: for a still (especially **long exposure**), the manager reconfigures to a still config with the requested `ExposureTime`, captures (JPEG and/or **raw DNG**), then restores preview.
- During a long exposure the **preview is necessarily paused** (same sensor). The UI shows a **countdown / progress bar** and a "preview paused — capturing" state pushed over the WebSocket.
- Short captures can reuse a still stream configured alongside preview (picamera2 supports a preview+still config) → no visible interruption for snapshots.

All picamera2 calls are **blocking** → run in a threadpool (`anyio.to_thread`), bridged to the async endpoints. A background capture thread updates the latest JPEG frame; the `/stream.mjpg` async generator awaits an `asyncio.Event` and yields the newest frame to each connected client.

### The other hard part: seeing stars in the preview at all
A standard video preview runs ~30 fps → **~33 ms exposure → nearly every star is invisible**.
Point the scope at a star with default settings and the screen is black. Two consequences that
shape the design:

1. **Star-preview mode is required.** For focusing on stars, the preview must run with long frame
   durations (0.5–2 s via libcamera `FrameDurationLimits`) and raised gain — the stream crawls at
   0.5–2 fps but actually shows stars. The UI (focus meter, sparkline) must degrade gracefully to
   that cadence. Moon/planets/terrestrial focusing works fine at normal video rates.
2. **Auto-exposure must be lockable, and manual controls come *before* star focusing.** As a star
   defocuses it dims; auto-exposure brightens the frame and confounds any sharpness metric.
   Focusing on the sky requires locked manual `ExposureTime`/`AnalogueGain` (+ AWB off). This is
   why manual controls (M3) are sequenced **before** on-sky focus assist (M4) in the roadmap.

### Focus data path (on device)
Two dev-phase shortcuts must be replaced on real hardware:
- **Analyze uncompressed luma, not the JPEG.** The dev implementation decodes the preview JPEG —
  fine on the mock, but JPEG quantization crushes faint-star signal exactly where it matters, and
  the decode is wasted CPU. picamera2 can deliver a **lores YUV stream** alongside the main one;
  the driver Protocol grows a "latest luma plane" method (the mock synthesizes it).
- **True 1:1 zoom via `ScalerCrop`.** CSS-zooming the downscaled preview is fine for framing but
  useless for critical focus. libcamera's `ScalerCrop` control crops a sensor region into the
  existing stream → real sensor pixels through the same MJPEG path, no reconfiguration.

---

## 5. Feature set

### Focus assist (the core value)
- **Digital zoom / ROI**: drag a region → analysis restricted to it; true 1:1 sensor-pixel zoom
  via `ScalerCrop` on hardware (CSS zoom on the mock).
- **Focus score, two modes** shown as a **live bar + rolling graph** — turn the focuser to
  maximize it. This is the killer feature the old repo never had.
  - **Scene mode** (Moon, planets, terrestrial): variance-of-Laplacian. Great on detailed scenes,
    but shot noise *is* high-frequency signal, so it's unreliable on a lone star against black.
  - **Star mode** (night default): **HFD** (half-flux diameter, minimize) and/or **peak intensity**
    (maximize) on the brightest star in the ROI — what SharpCap/NINA use; stable and near-linear
    near focus. Pairs with star-preview mode (§4).
- **Overlays**: crosshair, rule-of-thirds grid. (Focus **peaking** = backlog; needs a server-side
  processed overlay stream, and HFD + 1:1 zoom cover the need.)
- **Histogram** (log scale — the dark-sky background dominates a linear plot) + clipping warning.
- A **Bahtinov mask** works naturally with the 1:1 zoom + crosshair; a spike-centering aid is a
  possible later refinement.

### Camera control (adapts to detected `CameraProfile`)
- Exposure time (slider bounded by sensor max), analogue gain (ISO), AWB off / manual, brightness/contrast/sharpness, resolution, rotation/flip.
- **Presets**: save/load named setting bundles (e.g. "Moon", "M42 subs").

### Capture
- Single still → **JPEG + optional raw DNG** (for stacking in Siril/DSS later).
- **Long exposure** with progress + countdown.
- **Sequence / intervalometer**: N frames × exposure × interval (light-frame subs).
- Auto-saved to `captures/` with metadata in SQLite (timestamp, settings, thumbnail).

### Gallery & system
- Thumbnail grid, full-view, **download to phone**, delete, free-space indicator.
- System panel: **CPU temp**, disk usage, uptime, AP SSID/clients, camera model.

### UX for astronomy
- **Mobile-first**, one-hand friendly, large touch targets (you're at a telescope in the dark).
- **Red night-vision theme** (red-on-black) to preserve dark adaptation — plus normal dark theme.
- **PWA**: installable, no address bar, works fully offline (it already is).

---

## 6. Proposed repository structure

```
pi-focus-camera/
├── backend/
│   ├── pyproject.toml            # uv-managed; core deps + optional [pi] group
│   ├── uv.lock                   # committed lockfile
│   ├── .python-version          # 3.14
│   ├── app/
│   │   ├── main.py               # Litestar app, lifespan, static SPA mount
│   │   ├── config.py             # env/settings (pydantic-settings)
│   │   ├── camera/
│   │   │   ├── base.py           # Camera driver Protocol (interface)
│   │   │   ├── manager.py        # CameraManager singleton (async-locked)
│   │   │   ├── profile.py        # CameraProfile capability detection
│   │   │   ├── stream.py         # MJPEG frame broker
│   │   │   ├── focus.py          # sharpness / histogram metrics (numpy)
│   │   │   ├── mock.py           # MockCamera — test pattern, dev without hardware
│   │   │   └── picamera2_driver.py  # Picamera2Camera — Pi only, optional import
│   │   ├── controllers/
│   │   │   ├── stream.py         # GET /api/stream.mjpg
│   │   │   ├── live_ws.py        # WS  /api/live
│   │   │   ├── camera.py         # REST /api/camera/*
│   │   │   ├── capture.py        # REST /api/capture, sequences
│   │   │   ├── gallery.py        # REST /api/gallery/*
│   │   │   └── system.py         # REST /api/system, /health
│   │   ├── storage/              # SQLite models + captures dir helpers
│   │   └── static/               # ← built Svelte SPA copied here
│   └── tests/
├── frontend/
│   ├── package.json              # svelte, vite, (svelte-kit static optional)
│   ├── vite.config.ts
│   └── src/
│       ├── App.svelte
│       ├── lib/
│       │   ├── api.ts            # REST client
│       │   ├── live.ts           # WebSocket store
│       │   └── stores.ts         # camera state, theme (night mode)
│       └── components/
│           ├── LiveView.svelte   # MJPEG <img> + overlays + zoom
│           ├── FocusMeter.svelte
│           ├── Histogram.svelte
│           ├── Controls.svelte   # driven by CameraProfile
│           ├── CaptureBar.svelte
│           ├── Gallery.svelte
│           └── SystemPanel.svelte
├── deploy/
│   ├── astrocam.service          # systemd unit
│   ├── setup-ap.sh               # NetworkManager hotspot
│   ├── setup-mdns.sh             # avahi (astrocam.local)
│   └── install.sh                # one-shot provisioning
├── CONCEPT.md                    # this file
└── README.md
```

The old `src/` is retired (kept in git history) once `backend/` proves out.

---

## 7. Environments: uv + Python 3.14, and the picamera2 catch

**Dev (any machine, no camera) — the default:**
```bash
uv sync                         # Python 3.14 venv from uv.lock, core deps only
uv run litestar --app app.main:app run --reload   # MockCamera drives a test-pattern stream
```
uv manages the interpreter and deps end-to-end. No camera libraries involved — the app talks
to the `Camera` Protocol and picks `MockCamera` when picamera2 can't be imported.

**Device (the Pi) — the catch to plan around:**
`picamera2` binds to `libcamera`. Two ways to get it, and they interact badly with a
uv-managed **Python 3.14**:

- **A. Pip-installable stack (keeps uv + 3.14):**
  ```bash
  uv sync --extra pi           # adds picamera2 + rpi-libcamera + rpi-kms
  ```
  Clean if wheels exist for your Python/libcamera combo. **Risk:** `rpi-libcamera` is niche and
  must match the system libcamera; wheels for a brand-new 3.14 may lag. Verify on the real Pi.

- **B. System apt package (most reliable, but pins Python):**
  `python3-picamera2` is built against the OS's **system Python (3.13 on Trixie)**, and a
  uv-downloaded standalone 3.14 **cannot see apt site-packages**. If A doesn't work, run the app
  on the device with the interpreter picamera2 supports:
  ```bash
  sudo apt install -y python3-picamera2 python3-libcamera avahi-daemon
  uv venv --system-site-packages --python /usr/bin/python3   # bridge to apt packages
  uv pip install -e .          # litestar, uvicorn, numpy, aiosqlite...
  ```

Because the camera lives behind the driver Protocol, **path B pins only the on-device interpreter**
— all app code, tests, and dev stay on uv + 3.14 unchanged. Decide A vs. B once, on the actual Pi,
by trying A first. Sanity check hardware: `rpicam-hello --list-cameras`.

### WiFi access point (NetworkManager)
```bash
nmcli device wifi hotspot ifname wlan0 ssid AstroCam password "<8+ chars>"
nmcli connection modify Hotspot connection.autoconnect yes
```
NM's shared mode gives DHCP + DNS automatically; the Pi is reachable at **10.42.0.1**.
`avahi` adds **http://astrocam.local** so users don't type an IP. (Optional: captive-portal
redirect so joining the network pops the GUI automatically.)

### App as a service
```ini
# deploy/astrocam.service
[Unit]
Description=Prime Focus Camera
After=network.target
[Service]
ExecStart=/home/dfrei/.../backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
WorkingDirectory=/home/dfrei/.../backend
Restart=on-failure
[Install]
WantedBy=multi-user.target
```
Litestar serves the built SPA as static files → **one process, one port, no Node at runtime**.

### Build the frontend
```bash
cd frontend && npm ci && npm run build     # → dist/
cp -r dist/* ../backend/app/static/        # bundled with the app
```
Do this on the Pi or a laptop; ship `static/` to the Pi.

---

## 8. Roadmap / milestones

Ordering rationale: manual exposure control (M3) **precedes** on-sky focus assist (M4), because
locked exposure + star-preview mode are prerequisites for any focus metric to work on stars (§4).

**M0 — Skeleton (no hardware needed). ✅ done.** Litestar app + Svelte SPA served static; mock
camera streaming a test pattern over MJPEG; WebSocket telemetry loop. Dev on any machine.

**M1 — Live view on real camera. ✅ code done — needs on-Pi verification.** picamera2 preview →
MJPEG broker; `CameraProfile` detection; `scripts/probe_camera.py`. Verify with camera attached.

**M2 — Focus assist v1. ✅ done (mock-verified).** Laplacian focus score + sparkline, log
histogram + clipping, drag-ROI, CSS zoom, overlays, night theme.

**M3 — Camera controls & star preview. ✅ core done (mock-verified); on-Pi run open.** Manual
exposure/gain sliders bounded by `CameraProfile`, **AE/AWB lock**, control validation (typed
`CameraSettings`, no raw dict pass-through), **star-preview mode** (long `FrameDurationLimits`,
slow-cadence UI), SQLite presets. (Brightness/contrast/sharpness + rotation/flip + resolution
deferred — don't block M4.)

**M4 — Focus assist v2 (on-sky). ✅ core done (mock-verified); on-Pi V-curve + 1:1 zoom open.**
**HFD/peak star metric** (night default) with Scene/Star mode toggle; analyze the **lores luma
plane** instead of decoded JPEG; **`ScalerCrop` 1:1 zoom**. First real star-focus session (the
V-curve) happens on the Pi. *This is the minimum genuinely useful product on the sky.*

**M5 — Capture.** Single still (JPEG + raw DNG), long-exposure with progress + preview-paused UX,
gallery + download, SQLite metadata. (Productive deep-sky capture expects the HQ sensor — §1.)

**M6 — Sequences + system.** Intervalometer, system panel, PWA/offline polish.

**M7 — Deployment.** AP + mDNS + systemd scripts, one-shot `install.sh`, README.

Ship is useful for Moon/planets at **M2+M3**; genuinely useful on stars at **M4**; astro-complete
at **M5**.

---

## 9. Open questions / decisions to revisit

1. **Server**: uvicorn (simplest) vs **granian** (Rust, lighter on Pi). Start uvicorn, switch if needed.
2. **Storage location**: onboard SD vs USB stick for captures (raw DNGs are large). Make the
   captures dir configurable; recommend a USB drive for real sessions.
3. **Auth**: the old repo had an API key. On a private AP it's arguably unnecessary — recommend
   **no auth** for v1 (single-user, isolated network), revisit only if the Pi ever shares a LAN.
4. **Captive portal**: nice-to-have so the GUI auto-opens on join; adds complexity → post-M6.
5. **Stacking**: out of scope on the Pi (CPU-bound). Export raw DNG subs; stack on a laptop
   (Siril/DeepSkyStacker). Could add on-Pi stacking much later if wanted.
6. **Planetary video-burst mode** ("lucky imaging": short raw video runs at max fps, keep the
   sharpest frames): the mode the V2 is actually best at for planets. Not in M0–M7; candidate
   for the first post-v1 feature, likely alongside the HQ upgrade.
7. **Dev/device Python skew**: dev runs 3.14, device likely 3.13 (deploy Path B). Guardrails:
   `requires-python >=3.13`, ruff `target-version = py313` (lint to the floor, not the dev
   version), and eventually CI running tests on 3.13. One 3.14-only construct would otherwise
   only fail at deploy time.
8. **When to stop**: if ambitions grow toward guiding, plate-solving, or full session automation,
   the honest answer becomes "run INDI/Ekos". This project's niche is the zero-config, offline,
   phone-first focus + capture tool — keep it that.
