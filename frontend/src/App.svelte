<script lang="ts">
  import { onMount } from 'svelte'
  import LiveView from './components/LiveView.svelte'
  import FocusMeter from './components/FocusMeter.svelte'
  import Histogram from './components/Histogram.svelte'
  import Controls from './components/Controls.svelte'
  import CaptureBar from './components/CaptureBar.svelte'
  import SequenceBar from './components/SequenceBar.svelte'
  import Gallery from './components/Gallery.svelte'
  import SystemPanel from './components/SystemPanel.svelte'
  import Help from './components/Help.svelte'
  import { connected, connectLive } from './lib/live'
  import { nightMode, dimLevel } from './lib/stores'

  type Tab = 'live' | 'gallery' | 'system'
  let tab = $state<Tab>('live')
  let helpOpen = $state(false)

  onMount(() => {
    connectLive()
  })

  // Apply the night-vision theme + screen dimmer to the document root.
  $effect(() => {
    document.documentElement.dataset.night = $nightMode ? 'on' : 'off'
  })
  $effect(() => {
    document.documentElement.style.filter = $dimLevel < 1 ? `brightness(${$dimLevel})` : ''
  })
</script>

<header>
  <div class="brand">
    <span class="dot" class:on={$connected} title={$connected ? 'connected' : 'reconnecting…'}></span>
    <h1>AstroCam</h1>
  </div>
  <div class="actions">
    <label class="dim" title="Screen brightness">
      <svg viewBox="0 0 24 24" aria-hidden="true"
        ><circle cx="12" cy="12" r="4" /><path
          d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"
        /></svg
      >
      <input type="range" min="0.3" max="1" step="0.05" bind:value={$dimLevel} />
    </label>
    <button
      class="icon"
      class:active={$nightMode}
      onclick={() => nightMode.update((v) => !v)}
      title="Night mode"
      aria-label="Toggle night mode"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"
        ><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" fill="currentColor" stroke="none" /></svg
      >
    </button>
    <button class="icon" onclick={() => (helpOpen = true)} title="Help" aria-label="Help">?</button>
  </div>
</header>

<Help bind:open={helpOpen} />

<main>
  {#if tab === 'live'}
    <LiveView />
    <div class="focus-row">
      <FocusMeter />
      <Histogram />
    </div>
    <CaptureBar />
    <SequenceBar />
    <Controls />
  {:else if tab === 'gallery'}
    <Gallery />
  {:else}
    <SystemPanel />
  {/if}
</main>

<nav class="tabbar">
  <button class:active={tab === 'live'} onclick={() => (tab = 'live')}>
    <svg viewBox="0 0 24 24" aria-hidden="true"
      ><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg
    >
    <span>Live</span>
  </button>
  <button class:active={tab === 'gallery'} onclick={() => (tab = 'gallery')}>
    <svg viewBox="0 0 24 24" aria-hidden="true"
      ><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path
        d="M4 16l4.5-4.5 3 3L15 11l5 5"
      /></svg
    >
    <span>Gallery</span>
  </button>
  <button class:active={tab === 'system'} onclick={() => (tab = 'system')}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2 6 4-15 2.5 9H21" /></svg>
    <span>System</span>
  </button>
</nav>

<style>
  header {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.7rem 1rem;
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }
  h1 {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    margin: 0;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--muted);
    flex: none;
  }
  .dot.on {
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .dim {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--muted);
  }
  .dim svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
  .dim input {
    width: 60px;
    accent-color: var(--accent);
  }
  @media (max-width: 520px) {
    .dim input {
      width: 40px;
    }
  }
  .icon {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 9px;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .icon.active {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
  }
  .icon svg {
    width: 18px;
    height: 18px;
  }
  main {
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem 1rem calc(72px + env(safe-area-inset-bottom, 0px));
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
  .tabbar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 10;
    display: flex;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    background: color-mix(in srgb, var(--bg) 90%, transparent);
    backdrop-filter: blur(10px);
    border-top: 1px solid var(--line);
  }
  .tabbar button {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
    padding: 0.5rem 0 0.55rem;
    background: transparent;
    border: none;
    color: var(--muted);
    font-size: 0.7rem;
    cursor: pointer;
  }
  .tabbar button.active {
    color: var(--accent);
  }
  .tabbar svg {
    width: 23px;
    height: 23px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.7;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>
