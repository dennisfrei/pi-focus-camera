<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { getSystem, setFocusRoi, setFocusZoom, type Roi } from '../lib/api'

  // Live MJPEG preview with a focus ROI you can draw, a digital zoom into that ROI, and overlays.
  // On real hardware the zoom is a true 1:1 sensor crop (ScalerCrop) through the same stream; on
  // the mock there's no sensor to crop, so we CSS-scale the downscaled preview instead.
  let loaded = $state(false)
  let errored = $state(false)
  let showGrid = $state(false)
  let zoomed = $state(false)
  let hwZoom = $state(false)
  let roi = $state<Roi>(null)

  onMount(() => {
    getSystem()
      .then((s) => (hwZoom = s.profile.supports_hw_zoom))
      .catch(() => {})
  })

  let viewport: HTMLDivElement
  let dragging = $state(false)
  let start = { x: 0, y: 0 }
  let cur = $state({ x: 0, y: 0 })

  // The MJPEG <img> is a single long-lived connection; unlike the WebSocket it has no auto-reconnect,
  // so on a long session a dropped connection leaves a black frame. Re-point the src (new
  // cache-buster) to reconnect — on load error, and via a manual Reload button.
  let src = $state(`/api/stream.mjpg?t=${Date.now()}`)
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined

  function reconnectStream() {
    clearTimeout(reconnectTimer)
    loaded = false
    src = `/api/stream.mjpg?t=${Date.now()}`
  }

  function onStreamError() {
    errored = true
    clearTimeout(reconnectTimer) // don't stack timers across repeated error events
    reconnectTimer = setTimeout(reconnectStream, 1500)
  }

  // On unmount (e.g. switching to the Gallery tab) stop any pending retry and drop the stream src so
  // the browser aborts the never-ending MJPEG connection instead of leaving a zombie broker client.
  onDestroy(() => {
    clearTimeout(reconnectTimer)
    src = ''
  })

  // Selection rectangle (normalized) currently being drawn.
  let sel = $derived(
    dragging
      ? {
          x0: Math.min(start.x, cur.x),
          y0: Math.min(start.y, cur.y),
          x1: Math.max(start.x, cur.x),
          y1: Math.max(start.y, cur.y),
        }
      : null,
  )

  // CSS transform that makes the ROI fill the viewport (top-left origin; uniform, no distortion).
  // Skipped when the hardware does the crop for real — then the stream itself is already zoomed.
  let transform = $derived.by(() => {
    if (!zoomed || !roi || hwZoom) return 'none'
    const [x0, y0, x1, y1] = roi
    const s = 1 / Math.max(x1 - x0, y1 - y0)
    return `scale(${s}) translate(${-x0 * 100}%, ${-y0 * 100}%)`
  })

  async function toggleZoom() {
    zoomed = !zoomed
    if (hwZoom) await setFocusZoom(zoomed && roi ? roi : null)
  }

  function norm(e: PointerEvent) {
    const r = viewport.getBoundingClientRect()
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    }
  }

  function onDown(e: PointerEvent) {
    if (zoomed) return // don't draw while zoomed in
    dragging = true
    start = norm(e)
    cur = start
    viewport.setPointerCapture(e.pointerId)
  }

  function onMove(e: PointerEvent) {
    if (dragging) cur = norm(e)
  }

  async function onUp() {
    if (!dragging) return
    const box = sel // snapshot before clearing `dragging` (which resets the derived `sel` to null)
    dragging = false
    if (box && box.x1 - box.x0 > 0.02 && box.y1 - box.y0 > 0.02) {
      roi = [box.x0, box.y0, box.x1, box.y1]
      await setFocusRoi(roi)
    }
  }

  async function clearRoi() {
    if (zoomed && hwZoom) await setFocusZoom(null)
    roi = null
    zoomed = false
    await setFocusRoi(null)
  }
</script>

<div class="tools">
  <button onclick={() => (showGrid = !showGrid)} class:active={showGrid}>Grid</button>
  <button onclick={toggleZoom} disabled={!roi} class:active={zoomed}>
    Zoom{hwZoom ? ' 1:1' : ''}
  </button>
  <button onclick={clearRoi} disabled={!roi}>Clear ROI</button>
  <button onclick={reconnectStream} title="Reconnect the preview stream">Reload</button>
  <span class="hint">{roi ? 'ROI set' : 'drag on the image to set a focus region'}</span>
</div>

<div
  class="viewport"
  role="application"
  aria-label="Live camera preview — drag to select a focus region"
  bind:this={viewport}
  onpointerdown={onDown}
  onpointermove={onMove}
  onpointerup={onUp}
>
  {#if !loaded && !errored}
    <div class="placeholder">connecting to camera…</div>
  {/if}
  {#if errored}
    <div class="placeholder error">no stream — is the backend running?</div>
  {/if}

  <img
    {src}
    alt="Live camera preview"
    class:hidden={!loaded}
    style:transform
    onload={() => {
      loaded = true
      errored = false
    }}
    onerror={onStreamError}
  />

  {#if showGrid}
    <div class="grid" aria-hidden="true">
      <span style="left:33.33%"></span><span style="left:66.66%"></span>
      <span class="h" style="top:33.33%"></span><span class="h" style="top:66.66%"></span>
    </div>
  {/if}

  <div class="crosshair" aria-hidden="true"><span class="v"></span><span class="h"></span></div>

  {#if sel}
    <div
      class="roi drawing"
      style="left:{sel.x0 * 100}%;top:{sel.y0 * 100}%;width:{(sel.x1 - sel.x0) * 100}%;height:{(sel.y1 - sel.y0) * 100}%"
    ></div>
  {:else if roi && !zoomed}
    <div
      class="roi"
      style="left:{roi[0] * 100}%;top:{roi[1] * 100}%;width:{(roi[2] - roi[0]) * 100}%;height:{(roi[3] - roi[1]) * 100}%"
    ></div>
  {/if}
</div>

<style>
  .tools {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }
  .tools button {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .tools button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .tools button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .hint {
    color: var(--muted);
    font-size: 0.75rem;
    margin-left: auto;
  }
  .viewport {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #000;
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
    display: grid;
    place-items: center;
    touch-action: none;
    cursor: crosshair;
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
    transform-origin: 0 0;
  }
  img.hidden {
    visibility: hidden;
  }
  .placeholder {
    position: absolute;
    color: var(--muted);
    font-size: 0.9rem;
  }
  .placeholder.error {
    color: var(--accent);
  }
  .crosshair .v,
  .crosshair .h,
  .grid span {
    position: absolute;
    background: color-mix(in srgb, var(--accent) 45%, transparent);
    pointer-events: none;
  }
  .crosshair .v {
    top: 0;
    bottom: 0;
    left: 50%;
    width: 1px;
  }
  .crosshair .h {
    left: 0;
    right: 0;
    top: 50%;
    height: 1px;
  }
  .grid span {
    top: 0;
    bottom: 0;
    width: 1px;
    background: color-mix(in srgb, var(--accent) 25%, transparent);
  }
  .grid span.h {
    left: 0;
    right: 0;
    top: auto;
    bottom: auto;
    width: auto;
    height: 1px;
  }
  .roi {
    position: absolute;
    border: 1.5px solid var(--accent);
    box-shadow: 0 0 0 100vmax color-mix(in srgb, #000 45%, transparent);
    pointer-events: none;
  }
  .roi.drawing {
    border-style: dashed;
  }
</style>
