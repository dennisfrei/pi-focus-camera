<script lang="ts">
  import { live } from '../lib/live'

  let hist = $derived($live?.histogram ?? [])
  let max = $derived(Math.max(1, ...hist))
  let clipping = $derived($live?.clipping ?? 0)

  // Astro scenes are dominated by the dark-sky background (~99% of pixels in the low bins), so a
  // linear scale collapses to a single bar. A log scale reveals the shape and the faint star tail.
  const barHeight = (count: number) => (Math.log1p(count) / Math.log1p(max)) * 100
</script>

<div class="histogram">
  <div class="head">
    <span class="label">Histogram</span>
    {#if clipping > 0.005}
      <span class="clip">⚠ {(clipping * 100).toFixed(1)}% clipped</span>
    {/if}
  </div>
  <div class="bars">
    {#each hist as count}
      <span style:height="{barHeight(count)}%"></span>
    {/each}
  </div>
  <div class="axis"><span>shadows</span><span>log scale</span><span>highlights</span></div>
</div>

<style>
  .histogram {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.4rem;
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .clip {
    color: var(--accent);
    font-size: 0.72rem;
  }
  .bars {
    display: flex;
    align-items: flex-end;
    gap: 1px;
    height: 70px;
  }
  .bars span {
    flex: 1;
    background: color-mix(in srgb, var(--accent) 70%, var(--fg));
    min-height: 1px;
    border-radius: 1px 1px 0 0;
  }
  .axis {
    display: flex;
    justify-content: space-between;
    margin-top: 0.25rem;
    color: var(--muted);
    font-size: 0.62rem;
  }
</style>
