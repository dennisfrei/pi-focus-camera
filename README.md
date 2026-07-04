# Prime Focus Camera

Turn a Raspberry Pi + camera module into a **prime-focus camera for a telescope**. The Pi runs
everything, is its own WiFi access point, and a phone connects to a local web GUI to **focus**,
adjust camera settings, and **capture** — fully offline.

- **[MANUAL.md](MANUAL.md)** — setup, configuration & deployment (the operator's guide)
- **[CONCEPT.md](CONCEPT.md)** — architecture & the *what/why*
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** — the step-by-step build plan (milestones M0–M7)
  and the **known-issues register** from the latest code review

> Status: **M0–M7 feature-complete, mock-verified.** Every milestone — live view, focus assist
> (Scene + Star/HFD), manual controls & star preview, capture + gallery, intervalometer, system
> panel, PWA, and deploy scripts — is built and tested against the mock camera. The parts that need
> real hardware are written but **not yet verified on the Pi**: the picamera2 live view (M1), the
> on-sky HFD V-curve + 1:1 `ScalerCrop` zoom (M4), long-exposure/DNG capture (M5), and the on-phone
> PWA install over the access point (M6/M7). A full-branch code review (2026-07-04) found 10 issues
> to fix before/during the hardware session — see the register in
> [IMPLEMENTATION.md](IMPLEMENTATION.md#known-issues--code-review-2026-07-04).
>
> Honest scope: with the Camera Module V2 this is a **focus aid + lunar/planetary camera**;
> productive deep-sky capture expects the HQ (IMX477) upgrade — see CONCEPT §1.

## Stack

| Layer     | Choice                                                          |
|-----------|----------------------------------------------------------------|
| Backend   | Python 3.14 + [Litestar](https://litestar.dev), managed by [uv]|
| Camera    | picamera2 (libcamera) behind a driver interface; mock for dev  |
| Frontend  | Svelte 5 + Vite (static build; Node is build-time only)        |
| Networking| Pi as WiFi AP (NetworkManager) + mDNS (`astrocam.local`)       |

[uv]: https://docs.astral.sh/uv/

## Quickstart (dev, no camera)

```bash
# Backend — mock camera, live reload
cd backend
uv sync
uv run poe dev            # http://localhost:8080  (API + MJPEG stream)

# Frontend — Vite dev server, proxies /api to the backend
cd ../frontend
npm install
npm run dev               # open the printed URL
```

You should see a moving test-pattern live view and a status line fed by the WebSocket.

**API docs:** interactive Swagger UI at **`/api/docs`** (raw schema at `/api/docs/openapi.json`).
The Swagger assets are vendored under `backend/app/vendor/` so the docs work with **no internet**
on the Pi.

### Production build (single process)

```bash
cd frontend && npm run build     # outputs into backend/app/static/
cd ../backend && uv run poe serve
```

## On the Raspberry Pi

```bash
git clone <this repo> ~/pi-focus-camera
cd ~/pi-focus-camera
bash deploy/install.sh          # camera stack + venv + frontend build + systemd + mDNS
AP_SSID=AstroCam AP_PASS='choose-8+chars' sudo -E bash deploy/setup-ap.sh   # from a LOCAL session
```

Join the `AstroCam` WiFi on the phone and open **http://astrocam.local:8080**. Full instructions —
Path A vs. B for `picamera2`, configuration (`PFC_*` env vars), service operation, updating, and
troubleshooting — are in **[MANUAL.md](MANUAL.md)**.

## History

The original 2020 Flask/`picamera` prototype lives in `src/` and git history; it's being fully
replaced (see CONCEPT.md §2). It's kept until the new backend is confirmed streaming from the real
sensor on the Pi (milestone M1's hardware check), then removed.
