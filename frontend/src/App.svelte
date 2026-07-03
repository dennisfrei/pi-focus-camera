<script lang="ts">
  import { onMount } from 'svelte'
  import LiveView from './components/LiveView.svelte'
  import FocusMeter from './components/FocusMeter.svelte'
  import Histogram from './components/Histogram.svelte'
  import Controls from './components/Controls.svelte'
  import CaptureBar from './components/CaptureBar.svelte'
  import Gallery from './components/Gallery.svelte'
  import Help from './components/Help.svelte'
  import { live, connected, connectLive } from './lib/live'
  import { getSystem, type SystemInfo } from './lib/api'
  import { nightMode } from './lib/stores'

  let system = $state<SystemInfo | null>(null)
  let helpOpen = $state(false)

  onMount(() => {
    connectLive()
    getSystem().then((s) => (system = s)).catch(() => {})
  })

  // Apply the night-vision theme to the document root.
  $effect(() => {
    document.documentElement.dataset.night = $nightMode ? 'on' : 'off'
  })
</script>

<header>
  <div class="brand">
    <span class="dot" class:on={$connected}></span>
    <h1>Prime Focus Camera</h1>
  </div>
  <div class="actions">
    <button class="toggle" onclick={() => (helpOpen = true)} aria-label="Help">? Help</button>
    <button class="toggle" onclick={() => nightMode.update((v) => !v)}>
      {$nightMode ? '🔴 Night' : '⚪ Normal'}
    </button>
  </div>
</header>

<Help bind:open={helpOpen} />

<main>
  <LiveView />

  <div class="focus-row">
    <FocusMeter />
    <Histogram />
  </div>

  <CaptureBar />

  <Controls />

  <Gallery />

  <section class="status">
    <div class="row">
      <span class="label">Camera</span>
      <span class="value">{$live?.camera ?? system?.camera ?? '—'}</span>
    </div>
    <div class="row">
      <span class="label">State</span>
      <span class="value">{$live?.state ?? '—'}</span>
    </div>
    <div class="row">
      <span class="label">Link</span>
      <span class="value">{$connected ? 'connected' : 'reconnecting…'}</span>
    </div>
    {#if system}
      <div class="row">
        <span class="label">Resolution</span>
        <span class="value">{system.profile.resolution.join(' × ')}</span>
      </div>
      <div class="row">
        <span class="label">Max exposure</span>
        <span class="value">{(system.profile.exposure_us.max / 1_000_000).toFixed(1)} s</span>
      </div>
      {#if system.mock}
        <div class="badge">MOCK CAMERA — no hardware</div>
      {/if}
    {/if}
  </section>
</main>

<style>
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--line);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  h1 {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 0;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--muted);
  }
  .dot.on {
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }
  .actions {
    display: flex;
    gap: 0.4rem;
  }
  .toggle {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.7rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  main {
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .focus-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
  }
  @media (min-width: 640px) {
    .focus-row {
      grid-template-columns: 1fr 1fr;
    }
  }
  .status {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.5rem 0.9rem;
  }
  .row {
    display: flex;
    justify-content: space-between;
    padding: 0.35rem 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 50%, transparent);
    font-size: 0.9rem;
  }
  .row:last-of-type {
    border-bottom: none;
  }
  .label {
    color: var(--muted);
  }
  .value {
    font-variant-numeric: tabular-nums;
  }
  .badge {
    margin-top: 0.6rem;
    text-align: center;
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    color: var(--accent);
    border: 1px dashed color-mix(in srgb, var(--accent) 60%, transparent);
    border-radius: 8px;
    padding: 0.3rem;
  }
</style>
