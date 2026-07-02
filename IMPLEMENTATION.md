# Implementation Guide

Step-by-step build plan for the prime-focus camera. Companion to **[CONCEPT.md](CONCEPT.md)**
(the *what/why*); this file is the *how/in-what-order*. Each milestone lists concrete tasks, the
files they touch, and a **Done when** check. M0–M3 are verifiable on a dev machine via the mock;
M4+ "Done when" checks need the Pi with a camera (their *code* still develops against the mock).

Guiding rules:
- **Everything develops on the dev box via `MockCamera`.** Real hardware appears only for
  hardware verification and deploy.
- **Camera code lives behind `app/camera/base.py::Camera`** (a Protocol). Nothing outside the
  `camera/` package imports `picamera2`.
- **uv + Python 3.14** for the backend; **Node is build-time only** for the frontend.
  Lint to the deployment floor: ruff `target-version = py313` (device Path B runs 3.13).
- **Commit per milestone** — verified working states must land in git, not sit in the tree.
- Ship value early: useful for Moon/planets at **M2+M3**, genuinely useful on stars at **M4**,
  astro-complete at **M5**.
- Ordering: manual exposure (M3) comes **before** on-sky focus (M4) — a focus metric on stars
  needs locked exposure and a star-preview mode first (CONCEPT §4).

---

## Conventions

| Thing            | Choice                                                                 |
|------------------|------------------------------------------------------------------------|
| Python           | 3.14, managed by `uv` (`.python-version`, `uv.lock` committed)          |
| Web framework    | Litestar (ASGI), run via `uv run litestar ... run` / uvicorn           |
| Async bridge     | picamera2 calls are blocking → `anyio.to_thread.run_sync`              |
| Frontend         | Svelte 5 + Vite SPA, TypeScript                                         |
| Data             | SQLite via `aiosqlite` (captures metadata, presets)                     |
| Image math       | `numpy` (focus metric, histogram)                                      |
| Lint/format      | `ruff` (py), `prettier` + `svelte-check` (fe)                          |
| Tests            | `pytest` + `pytest-asyncio` (backend), drive endpoints against Mock    |

**Dev loop:** `uv run poe dev` (backend, reload) + `npm run dev` (frontend, Vite proxy → :8080).
**Prod:** `npm run build` → copy `dist/` into `backend/app/static/` → one Litestar process.

---

## M0 — Skeleton & mock stream  ← *scaffold now*

Goal: a running app on the dev box. Test-pattern MJPEG in the browser, live telemetry over WS,
health endpoint, Svelte shell that shows the stream.

**Backend**
- `uv init` the `backend/` project; add `litestar`, `uvicorn[standard]`, `anyio`, `numpy`,
  `pydantic-settings`, `pillow`; dev group `ruff`, `pytest`, `pytest-asyncio`. Pi camera stack
  lives in `requirements-pi.txt`, *not* in pyproject — it doesn't resolve on a dev box.
- `app/camera/base.py` — `Camera` Protocol: `start()/stop()`, `frames() -> AsyncIterator[bytes]`
  (JPEG), `profile -> CameraProfile`, `get_controls()/set_controls()`, `capture_still(...)`.
- `app/camera/mock.py` — `MockCamera`: numpy-drawn moving test pattern → JPEG via Pillow,
  fabricated `CameraProfile` (fake exposure/gain limits) so the UI has something to render.
- `app/camera/stream.py` — frame broker: latest-JPEG holder + `asyncio.Event` fan-out to N clients.
- `app/camera/manager.py` — singleton, async lock, selects driver (Mock unless picamera2 imports).
- `app/controllers/stream.py` — `GET /api/stream.mjpg` (multipart/x-mixed-replace).
- `app/controllers/live_ws.py` — `WS /api/live`: pushes `{state, fps, ...}` ~2 Hz.
- `app/controllers/system.py` — `GET /api/health`, `GET /api/system` (stub temp/disk).
- `app/main.py` — Litestar app, lifespan starts/stops the manager, static mount for the SPA.
- `app/config.py` — `pydantic-settings` (host, port, captures dir, forced-mock flag).

**Frontend**
- `npm create vite@latest frontend -- --template svelte-ts`; add nothing heavy.
- `src/lib/api.ts`, `src/lib/live.ts` (WS store), `src/lib/stores.ts` (theme + state).
- `src/components/LiveView.svelte` — `<img src="/api/stream.mjpg">` + a status line from WS.
- `src/App.svelte` — shell with a night-mode toggle (red-on-black) placeholder.
- `vite.config.ts` — dev proxy `/api` → `http://localhost:8080`.

**Tooling**
- `deploy/` placeholder scripts (empty stubs w/ comments).
- Root `README.md` quickstart; keep old `src/` untouched for now.

**Done when:** `uv run poe dev` + `npm run dev`, open the Vite URL on the phone/laptop → moving
test pattern renders, WS status line updates, `GET /api/health` returns ok. No camera involved.

---

## M1 — Real camera live view (on the Pi)  ✅ *code done — needs on-Pi verification*

- `app/camera/picamera2_driver.py` — `Picamera2Camera` implementing `Camera`; low-res preview
  via `JpegEncoder` → broker (encoder-thread frames handed over with `call_soon_threadsafe`).
- `app/camera/profile.py` — `build_profile()` from `picam2.camera_controls`
  (`ExposureTime`/`AnalogueGain` min/max, sensor modes, raw availability).
- Manager auto-selects `Picamera2Camera`; constructing it doubles as detection (falls back to mock).
- `scripts/probe_camera.py` prints the detected profile as JSON — the one-command hardware check.
- Verify Path A (`uv pip install -r requirements-pi.txt`) vs Path B (apt + `--system-site-packages`)
  per CONCEPT §7.

**Done when:** on the Pi, live preview from the real sensor shows in the phone browser; profile
limits reflect the actual sensor (V2 ≈ 11.8 s max exposure). ← *the only part still open*

---

## M2 — Focus assist v1  ✅ *done (mock-verified)*

Shipped: `app/camera/focus.py` (variance-of-Laplacian + 64-bin histogram + clipping, optional
normalized ROI, throttled analyze loop at `focus_hz`), WS payload with metrics,
`GET /api/focus` / `POST /api/focus/roi`, `FocusMeter` (auto-scaled bar + sparkline),
`Histogram` (**log scale** — linear collapses on dark-sky frames), drag-ROI + CSS zoom + grid,
night theme.

Known dev-phase shortcuts, deliberately deferred to M4: metric runs on decoded JPEG (not luma
plane), zoom is CSS on the downscaled preview (not 1:1), Laplacian only (no star metric).

---

## M3 — Camera controls & star preview  ← *next; prerequisite for on-sky focus*

- `app/controllers/camera.py` — `PATCH /api/camera/settings` **validated against
  `CameraProfile`** (typed model, clamp/reject unknown keys — no raw dict into picamera2),
  exposure, gain, AWB off, brightness/contrast/sharpness, rotation/flip.
- **AE/AWB lock**: explicit auto vs manual mode; manual = `AeEnable=False` + fixed
  `ExposureTime`/`AnalogueGain`. The UI must show which mode is active.
- **Star-preview mode**: long `FrameDurationLimits` (0.5–2 s) + raised gain so stars are visible
  at all (CONCEPT §4); preview fps drops to 0.5–2 — FocusMeter/Histogram must handle the slow
  cadence (no fake-smooth animation, show "exposure…" state between frames).
- Presets: SQLite table + `GET/POST/DELETE /api/camera/presets` (e.g. "Moon", "Star focus").
- Frontend `Controls.svelte` — sliders bounded by the profile; mode toggle; preset save/load.
- Mock support: honor `ExposureTime`/`AnalogueGain` in the rendered image (brightness/noise) so
  controls are testable without hardware.

**Done when:** exposure/gain changes visibly alter the live view (mock and Pi); AE lock persists;
star-preview mode streams at ~1 fps with the UI degrading gracefully; presets survive restart.

---

## M4 — Focus assist v2 (on-sky)  ← *first genuinely useful release on stars*

- **Star metric**: HFD (half-flux diameter, minimize) + peak intensity on the brightest star in
  the ROI; mode toggle Scene (Laplacian) / Star (HFD) in the UI, Star = night default.
- **Luma-plane analysis**: `Camera` Protocol grows a "latest luma frame" method; real driver
  serves the picamera2 **lores YUV** plane (no JPEG decode, no quantization loss); mock
  synthesizes it.
- **`ScalerCrop` 1:1 zoom**: drag-ROI maps to a sensor-region crop through the existing stream —
  real sensor pixels for critical focus; replaces the CSS zoom on hardware.
- First real star-focus session: verify metric moves monotonically through focus on a real star.

**Done when:** on the Pi, pointing at a star in star-preview mode, racking the focuser through
focus produces a clean V-curve in HFD; 1:1 zoom shows actual sensor pixels.

---

## M5 — Capture  ← *astro-complete*

- `app/camera/manager.py` — capture path with **mode switching + async lock**; long-exposure
  reconfigures the still config, captures, restores preview; short snapshot uses preview+still config.
- `capture_still` → JPEG (+ optional **raw DNG**); save to captures dir; row in SQLite (ts,
  settings, thumbnail path).
- `app/controllers/capture.py` — `POST /api/capture` (returns id; progress over WS for long exp).
- `app/controllers/gallery.py` — list/thumbnail/download/delete.
- Frontend `CaptureBar.svelte` (shutter + long-exp countdown, "preview paused" state) and
  `Gallery.svelte` (grid, full view, download to phone, delete).

**Done when:** capture a still on the Pi, see it in the gallery, download it to the phone; a long
exposure shows a countdown and pauses preview, then resumes.

Scope note: with the V2 this is lunar/planetary + bright-target capture; productive deep-sky subs
expect the HQ sensor (CONCEPT §1). A planetary **video-burst mode** is deliberately out of scope
here (CONCEPT §9).

---

## M6 — Sequences & system panel

- Intervalometer: N frames × exposure × interval; sequence state/progress over WS; cancelable.
- `app/controllers/system.py` — real CPU temp, disk free, uptime, AP SSID/clients, camera model.
- Frontend `SystemPanel.svelte`; PWA manifest + service worker (installable, offline).

**Done when:** run a 5-frame sequence to completion; system panel shows real temp/disk; app is
installable on the phone and works with the phone in airplane mode (on the Pi's AP).

---

## M7 — Deployment

- `deploy/setup-ap.sh` — NetworkManager hotspot (SSID/pass), autoconnect, IP 10.42.0.1.
- `deploy/setup-mdns.sh` — install/enable avahi → `astrocam.local`.
- `deploy/astrocam.service` — systemd unit running the Litestar app on `:8080`, `Restart=on-failure`.
- `deploy/install.sh` — one-shot: apt deps, `uv sync` (Path A, fall back B), frontend build+copy,
  enable services.
- README: hardware setup, flashing, first-boot, troubleshooting.

**Done when:** fresh Pi + this repo → run `install.sh` → reboot → phone joins `AstroCam`, opens
`http://astrocam.local`, full app works with no internet.

---

## Retiring the old code

Keep `src/` until M1 confirms the new backend streams from real hardware. Then remove it (history
preserves it) and delete the stale `requirements.txt` / root `.env.example` in favor of the
`backend/` uv project and `deploy/` scripts.
