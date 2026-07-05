<script lang="ts">
  import {
    listCaptures,
    deleteCapture,
    thumbUrl,
    imageUrl,
    rawUrl,
    type Capture,
    type FrameType,
  } from '../lib/api'
  import { capturesChanged, bumpCaptures } from '../lib/stores'

  let items = $state<Capture[]>([])
  let selected = $state<Capture | null>(null)
  let filter = $state<'all' | FrameType>('all')

  const frameType = (c: Capture) => String(c.settings.frame_type ?? 'light')
  const shown = $derived(filter === 'all' ? items : items.filter((c) => frameType(c) === filter))

  async function load() {
    items = await listCaptures().catch(() => [])
  }

  // Load initially and whenever the capture set changes (new shot or a delete).
  $effect(() => {
    void $capturesChanged
    load()
  })

  async function remove(id: number) {
    await deleteCapture(id)
    if (selected?.id === id) selected = null
    bumpCaptures()
  }

  const fmt = (created: number) => new Date(created * 1000).toLocaleString()

  // The settings snapshot stored with each capture — the metadata astro users actually want.
  function fmtSettings(s: Record<string, number | boolean | string>): string {
    const parts: string[] = []
    if (s.frame_type) parts.push(String(s.frame_type))
    const us = Number(s.exposure_us)
    if (s.ae_enable) parts.push('auto exp')
    else if (us >= 1_000_000) parts.push(`${(us / 1_000_000).toFixed(1)} s`)
    else if (us >= 1000) parts.push(`${(us / 1000).toFixed(0)} ms`)
    else if (us) parts.push(`${us} µs`)
    if (s.gain != null) parts.push(`gain ${Number(s.gain).toFixed(1)}×`)
    if (s.preview_mode) parts.push(String(s.preview_mode))
    if (s.raw) parts.push('raw')
    return parts.join(' · ')
  }
</script>

<section class="gallery">
  <div class="head">
    <span class="label">Gallery</span>
    <div class="right">
      {#if items.length}
        <select bind:value={filter} class="filter" aria-label="Filter by frame type">
          <option value="all">All</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="flat">Flat</option>
          <option value="bias">Bias</option>
        </select>
      {/if}
      <span class="count">{shown.length}</span>
    </div>
  </div>

  {#if items.length === 0}
    <p class="empty">No captures yet — press Capture above.</p>
  {:else if shown.length === 0}
    <p class="empty">No {filter} frames.</p>
  {:else}
    <div class="grid">
      {#each shown as c (c.id)}
        <button class="tile" onclick={() => (selected = c)} title={fmt(c.created)}>
          <img src={thumbUrl(c.id)} alt="capture {c.id}" loading="lazy" />
          {#if frameType(c) !== 'light'}<span class="ftype">{frameType(c)}</span>{/if}
          {#if c.has_raw}<span class="raw">RAW</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</section>

{#if selected}
  <div
    class="backdrop"
    role="button"
    tabindex="-1"
    aria-label="Close"
    onclick={() => (selected = null)}
    onkeydown={(e) => e.key === 'Escape' && (selected = null)}
  ></div>
  <div class="viewer" role="dialog" aria-modal="true" aria-label="Capture {selected.id}">
    <img src={imageUrl(selected.id)} alt="capture {selected.id}" />
    <div class="meta">
      <div class="info">
        <span>{fmt(selected.created)} · {selected.width}×{selected.height}</span>
        <span class="settings">{fmtSettings(selected.settings)}</span>
      </div>
      <div class="acts">
        <a class="btn" href={imageUrl(selected.id)} download>Download JPEG</a>
        {#if selected.has_raw}
          <a class="btn" href={rawUrl(selected.id)} download>Raw</a>
        {/if}
        <button class="btn danger" onclick={() => remove(selected!.id)}>Delete</button>
        <button class="btn" onclick={() => (selected = null)}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .gallery {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .filter {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 7px;
    padding: 0.15rem 0.3rem;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .filter option {
    background: var(--bg);
    color: var(--fg);
  }
  .count {
    color: var(--muted);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }
  .empty {
    color: var(--muted);
    font-size: 0.8rem;
    margin: 0.3rem 0;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(84px, 1fr));
    gap: 0.4rem;
  }
  .tile {
    position: relative;
    padding: 0;
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    aspect-ratio: 4 / 3;
    background: #000;
    cursor: pointer;
  }
  .tile img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .tile .raw {
    position: absolute;
    top: 3px;
    right: 3px;
    font-size: 0.55rem;
    letter-spacing: 0.05em;
    background: color-mix(in srgb, #000 60%, transparent);
    color: var(--accent);
    padding: 0.05rem 0.25rem;
    border-radius: 4px;
  }
  .tile .ftype {
    position: absolute;
    top: 3px;
    left: 3px;
    font-size: 0.55rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    background: color-mix(in srgb, #000 60%, transparent);
    color: var(--fg);
    padding: 0.05rem 0.25rem;
    border-radius: 4px;
  }
  .backdrop {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, #000 78%, transparent);
    z-index: 20;
    border: none;
  }
  .viewer {
    position: fixed;
    z-index: 21;
    inset: 0;
    margin: auto;
    width: min(760px, 94vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }
  .viewer img {
    width: 100%;
    max-height: 72vh;
    object-fit: contain;
    background: #000;
  }
  .meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    padding: 0.6rem 0.8rem;
    flex-wrap: wrap;
    font-size: 0.8rem;
    color: var(--muted);
  }
  .info {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .settings {
    color: var(--accent);
    font-variant-numeric: tabular-nums;
  }
  .acts {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .btn {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.7rem;
    font-size: 0.82rem;
    cursor: pointer;
    text-decoration: none;
  }
  .btn.danger {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 50%, transparent);
  }
</style>
