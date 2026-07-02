# Prime Focus Camera

Turn a Raspberry Pi + camera module into a **prime-focus camera for a telescope**. The Pi runs
everything, is its own WiFi access point, and a phone connects to a local web GUI to **focus**,
adjust camera settings, and **capture** — fully offline.

- **[CONCEPT.md](CONCEPT.md)** — architecture & the *what/why*
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** — the step-by-step build plan (milestones M0–M7)

> Status: **M2 — focus assist v1** (mock-verified). M1's real-camera driver is written but awaits
> on-Pi verification. Next: M3 — manual camera controls & star-preview mode.
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

See [CONCEPT.md §7](CONCEPT.md) for the camera-stack install (the `picamera2` + Python 3.14
caveat, Path A vs. B) and [`backend/requirements-pi.txt`](backend/requirements-pi.txt). Deploy
scripts (WiFi AP, mDNS, systemd) live in `deploy/` and land in milestone M7.

## History

The original 2020 Flask/`picamera` prototype lives in `src/` and git history; it is being fully
replaced. See CONCEPT.md §2 for what changed and why.
