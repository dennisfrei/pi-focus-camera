# Hardware Session — What's Left To Do

Handoff for the first session **on the actual Raspberry Pi with the camera attached**. Everything in
this repo is built and **mock-verified** (55-ish pytest, ruff/format clean, frontend builds); nothing
below is a known bug. This is the list of things that can only be confirmed — or that were written
"blind" and will likely need small fixes — **on real hardware**, plus the deferred backlog.

Start by reading [MANUAL.md](MANUAL.md) §4 (deployment) and [CONCEPT.md](CONCEPT.md) §7 (the
picamera2 install caveat). Milestone context is in [IMPLEMENTATION.md](IMPLEMENTATION.md).

---

## 0. Get it running on the Pi

1. `rpicam-hello --list-cameras` — confirm the sensor is detected *before* anything else.
2. Provision: `bash deploy/install.sh` (uses deploy **Path B** — apt `python3-picamera2` + a
   `--system-site-packages` uv venv; pins deps from `uv.lock`). **Prefer this** — Path A
   (`uv sync --extra pi`) compiles `rpi-libcamera` from source against the system libcamera and is
   fragile; only use it if you specifically want to stay on Python 3.14 (needs
   `apt install -y libcap-dev cmake libcamera-dev` first). See CONCEPT §7.
3. Quick check without the service: from `backend/`, `.venv/bin/python scripts/probe_camera.py`
   should print the detected `CameraProfile` as JSON. **This is the fastest signal that the driver
   imports, the sensor is found, and `build_profile` reads sane values.**
   ⚠️ On Path B, **run via `.venv/bin/…`, not `uv run`** — `uv run`/`uv sync` recreate `.venv` on the
   pinned 3.14 without `--system-site-packages` and lose picamera2 (see MANUAL §4.1).
   ⚠️ If you did a *manual* Path B (not `install.sh`) and hit `numpy.dtype size changed … ABI` from
   simplejpeg, run `uv pip uninstall numpy` so the app uses apt's numpy (what picamera2 was built
   against). `install.sh` already skips pip numpy.
4. Run it: `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080` (or the installed
   `astrocam.service`), open the page, watch the log — `picamera2 available — using Picamera2Camera`
   means you're on real hardware; `Falling back to MockCamera` means it isn't (check the reason).

> The whole `app/camera/picamera2_driver.py` is the **only module never executed** in dev. Treat §1–§5
> below as "verify this driver," in dependency order.

---

## 1. M1 — Live preview from the real sensor  *(first thing to verify)*

**Verify:** live MJPEG preview shows in the phone browser; `CameraProfile` limits match the sensor
(V2/IMX219 ≈ 11.76 s max exposure, gain to ~16). The system panel should show the real model.

**Most likely to need attention** (`picamera2_driver.py`):
- `_start_sync` configures a `main` JPEG stream **plus a `lores` YUV420 stream** and calls
  `start_recording(JpegEncoder(), FileOutput(output), name="main")`. Confirm the `name="main"`
  encoder target and the dual-stream config are accepted by your picamera2 version.
- The encoder calls `_BrokerOutput.write` on its own thread; frames cross to the loop via
  `loop.call_soon_threadsafe`. Confirm frames actually flow (the preview isn't black/frozen).
- `build_profile` (`profile.py`) reads `camera_controls`/`camera_properties`/`sensor_modes`. Compare
  its JSON against `rpicam-hello`/known IMX219 values; adjust fallbacks if libcamera reports `None`s.
  *(Confirmed on hardware 2026-07-05: the IMX219 probes as `imx219`, gain 1–16, raw+hw-zoom True. The
  unconfigured `ExposureTime` max was a short 66 ms — `build_profile` now widens it from
  `sensor_modes['exposure_limits']` to the real ~11.76 s.)*

**If the preview is black on the sky** that's expected — it's a ~33 ms exposure. Switch to **Star**
preview (§3) with raised gain.

---

## 2. M3 — Controls & star preview on hardware

**Verify:** exposure/gain sliders visibly change the live image; **AE/AWB lock** holds (turn AE off,
the frame stops auto-brightening); **Star preview** drops the stream to ~1 fps with long
`FrameDurationLimits`; presets save/apply/survive a restart.

**Watch for** (a code-review fix that only manifests here):
- **Long manual exposure in *Normal* mode.** `settings.to_controls` now raises the
  `FrameDurationLimits` ceiling to fit a manual exposure > ~33 ms. Set e.g. 2 s in Normal mode and
  confirm the sensor actually integrates 2 s (not silently clamped). Star mode should also work.
- **⚠ Likely fix needed — long exposures in the *preview*.** libcamera only allows a long
  `ExposureTime` if the *video configuration's* `FrameDurationLimits` permits it. Our driver sets
  `FrameDurationLimits` at runtime via `set_controls` (in `to_controls`), **not** in
  `create_video_configuration` (`picamera2_driver._start_sync`). On some picamera2 versions the
  runtime value is clamped to the mode's default, so a 2 s / star-preview exposure won't actually
  take. If you see that, pass a wide `controls={"FrameDurationLimits": (min, sensor_max)}` (and
  possibly a raw stream size that selects the long-exposure sensor mode) into
  `create_video_configuration`. This is the most likely on-Pi driver tweak.
- All control changes run under the manager lock; a slider drag now commits once on release.

---

## 3. M4 — On-sky focus (the point of the app)

**Verify (the real "Done when"):** point at a star in Star preview, drag an ROI over it, rack the
focuser through focus and confirm:
- **HFD V-curve** — the HFD number dips to a clean minimum at focus and rises either side; **peak**
  rises to a maximum at focus. (Synthetic tests prove the math; only a real star proves the optics
  loop.)
- **1:1 zoom** — the "Zoom 1:1" button (shown because hardware reports `supports_hw_zoom`) crops the
  sensor via `ScalerCrop` and shows **actual sensor pixels**, not an upscaled preview.

**Most likely to need attention:**
- **Luma plane** — `get_luma()` does `capture_array("lores")[:h, :w]` assuming YUV420 Y occupies the
  first `h` rows. Confirm the shape/stride on your sensor; the focus metric reads this every tick
  **from the analyze worker thread** while the encoder runs — watch for contention or tearing.
- **`ScalerCrop` mapping** — `_full_crop()` uses `ScalerCropMaximum` (falls back to
  `PixelArraySize`); `_set_zoom_sync` maps the normalized ROI into that rectangle. The exact
  reference rectangle and orientation are the classic picamera2 gotcha — verify the zoom lands where
  you drew the ROI. Note the manager **clears the focus ROI when hw-zoom engages** (so the metric
  measures the whole cropped frame, not a crop-of-a-crop) — confirm that feels right.

---

## 4. M5 — Capture (stills, long exposure, DNG)

**Verify:** a still lands in the gallery and downloads to the phone; a **long exposure** shows the
countdown and "preview paused", then preview **resumes**; **raw** produces a real **DNG**;
**Cancel** aborts a long exposure; frame-type (light/dark/flat/bias) tags the file.

**Most likely to need attention** (`_capture_sync`, all untested):
- The sequence stop_recording → `create_still_configuration(raw={} if raw)` → `configure` → `start`
  → `capture_request` → `make_image("main")` → `save_dng(tempfile)` → **restore preview via
  `_start_sync`** is a lot of picamera2 API surface. Expect to adjust method names/args.
- **Post-capture restore (code-review fix #1).** After the still, `manager._do_capture` re-applies
  `to_controls(settings)` + the tracked zoom. **Confirm the preview comes back in the same mode**
  (star cadence / manual exposure / zoom), not default 30 fps auto — this was the subtlest bug and
  only shows on hardware.
- **"Capture (auto)"** — with AE on, the still must actually auto-meter (the driver passes
  `AeEnable=True`); with AE off it locks the manual exposure. Verify a dim target isn't captured at
  the stale 20 ms default.
- **DNG size/validity** — open a raw in Siril/DSS to confirm it's a real sensor DNG, not the JPEG.

---

## 5. M6 / M7 — System, PWA, deployment

**Verify:**
- **System panel** shows real CPU temp / disk / uptime (these already read real values — the dev box
  is itself a Pi). Confirm the >75 °C and <1 GB **warnings** trigger when appropriate.
- **Power controls** — with `PFC_ENABLE_POWER_CONTROLS=true` (the service sets it) the Shut down /
  Reboot buttons appear and work (sudoers rule from `install.sh`). Test reboot once.
- **Access point** — run `deploy/setup-ap.sh` from a *local console* (it drops WiFi). Join `AstroCam`
  on the phone, reach `http://astrocam.local:8080`.
- **PWA install on the phone** — "Add to Home Screen", confirm the astro reticle icon and that it
  launches standalone and works with the phone in **airplane mode** on the Pi's AP. (iOS uses the new
  `apple-touch-icon.png`.)

**Still TODO in deployment:**
- **AP SSID + connected-client count** in the system panel — deferred to when the AP exists. Add a
  best-effort `nmcli`-based read to `controllers/system.py` (`system_info`) and a row in
  `SystemPanel.svelte`.
- Consider a captive-portal redirect so joining the AP pops the GUI (CONCEPT §9.4) — optional.

---

## 6. Performance pass (do this *on* the Pi — payoff is Pi-only)

Best measured with `journalctl`/`htop`/the temp readout under real load:
- **Idle-pause** the focus analyze loop **and** the JPEG encoder when there are **0** stream/WS
  subscribers (track a subscriber count in `FrameBroker`/`live_ws`). Big thermal/CPU win for a field
  device left on.
- **Smaller lores stream** for focus — `_start_sync` requests lores at full preview size; drop it to
  ~640×360 (HFD on the brightest star is resolution-tolerant; 1:1 zoom still uses `ScalerCrop`). ~4×
  less numpy per tick.
- **WS payload** — `live_ws` rebuilds + re-serializes the same dict per client at 5 Hz; serialize
  once per tick and/or skip unchanged `settings`/`sequence` blocks.
- **Configurable preview fps** for the real driver (`PFC_PREVIEW_FPS` → `FrameDurationLimits` on the
  video config) to trade smoothness for CPU/heat.
- **Gallery pagination** — `list_captures` returns every row and the UI renders every thumbnail; add
  `LIMIT/OFFSET` (or a created-cursor) + "load more" for long sessions.

---

## 7. Feature backlog (not started, by value)

- **V-curve / best-focus tracker** *(highest value; explicitly deferred so far)* — record HFD while
  racking the focuser, mark and display the minimum ("best: 3.2 px @ 21:42"). Turns the M4 metric
  into an actual focusing procedure.
- **Gallery download-as-zip** — a backend endpoint that zips selected captures (JPEG + raw) into one
  download; pairs with the existing multi-select. (Bulk *delete* already shipped.)
- **Multi-client settings sync** — `Controls.svelte` keeps local state; the WS already broadcasts
  `settings`, so reconcile it in when the panel isn't mid-edit (edge case; single-user is the design).
- **Low-disk auto-stop** — abort a running sequence when free space drops below a threshold.
- **Bahtinov / spike-centering aid**, **focus peaking** — CONCEPT §5 backlog.
- **Planetary video-burst / lucky-imaging mode** — the mode the V2 is actually best at (CONCEPT §9.6).

---

## 8. Open minor issues (tracked, not blocking)

- Per-operation SQLite connections (fine at this scale).
- PWA service worker is one-reload-behind after an update (cache-first shell) — reload once to update.
- No frontend unit tests (svelte-check only); no `TypedDict`s on the WS state dicts (no mypy in CI).

---

## 9. Cleanup gated on M1 hardware confirmation

Once §1 confirms the new backend streams from the real sensor:
- Delete the old prototype `src/` and the stale root `requirements.txt` (git history preserves them)
  — see IMPLEMENTATION.md "Retiring the old code". `readme.md` and the old root `.env.example` were
  already removed.
- Flip the status lines in README/CONCEPT/IMPLEMENTATION from "mock-verified / on-Pi open" to
  hardware-confirmed for each milestone as you tick them off.

---

### One-line summary for the new session

> The app is feature-complete and mock-verified. Your job on the Pi: **make `picamera2_driver.py`
> real** (§1→§5, in order — probe first, then live view, controls, focus V-curve, capture/DNG),
> then the perf pass (§6). Everything else is backlog.
