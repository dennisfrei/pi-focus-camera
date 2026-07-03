<script lang="ts">
  import { live } from '../lib/live'
  import { capture } from '../lib/api'
  import { bumpCaptures } from '../lib/stores'

  // Shutter for a single still. Uses the current exposure/gain; a long exposure pauses the preview
  // and counts down. "Raw" also saves the sensor frame (DNG on the Pi) for stacking later.
  let raw = $state(false)
  let error = $state<string | null>(null)

  const cap = $derived($live?.capture)
  const settings = $derived($live?.settings)
  const busy = $derived(cap?.active ?? false)

  // What the shutter will do: auto exposure, or the manual exposure that'll be used.
  const shutterLabel = $derived.by(() => {
    if (!settings) return 'Capture'
    if (settings.ae_enable) return 'Capture (auto)'
    const us = settings.exposure_us
    if (us >= 1_000_000) return `Capture ${(us / 1_000_000).toFixed(1)} s`
    if (us >= 1000) return `Capture ${(us / 1000).toFixed(0)} ms`
    return `Capture ${us} µs`
  })

  async function shoot() {
    error = null
    try {
      await capture({ raw })
      bumpCaptures()
    } catch {
      error = 'capture failed'
    }
  }
</script>

<section class="capturebar">
  {#if busy && cap}
    <div class="progress">
      <div class="prow">
        <span class="paused">● preview paused — capturing</span>
        <span class="count">{cap.remaining_s.toFixed(1)} s</span>
      </div>
      <div class="track"><div class="fill" style:width="{cap.progress * 100}%"></div></div>
    </div>
  {:else}
    <button class="shutter" onclick={shoot}>{shutterLabel}</button>
    <label class="raw">
      <input type="checkbox" bind:checked={raw} />
      Raw
    </label>
  {/if}
  {#if error}<span class="err">{error}</span>{/if}
</section>

<style>
  .capturebar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
  }
  .shutter {
    flex: 1;
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 8px;
    padding: 0.6rem;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
  }
  :root[data-night='on'] .shutter {
    color: #000;
  }
  .raw {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .raw input {
    accent-color: var(--accent);
  }
  .progress {
    flex: 1;
  }
  .prow {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    margin-bottom: 0.35rem;
  }
  .paused {
    color: var(--accent);
  }
  .count {
    font-variant-numeric: tabular-nums;
    color: var(--fg);
  }
  .track {
    height: 10px;
    background: color-mix(in srgb, var(--line) 60%, transparent);
    border-radius: 6px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.15s linear;
  }
  .err {
    color: var(--accent);
    font-size: 0.8rem;
  }
</style>
