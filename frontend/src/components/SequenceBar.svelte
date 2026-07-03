<script lang="ts">
  import { live } from '../lib/live'
  import { startSequence, cancelSequence } from '../lib/api'
  import { bumpCaptures } from '../lib/stores'

  // Intervalometer: N frames at the current exposure, with a gap between them. Each frame lands in
  // the gallery; progress comes over the WebSocket.
  let count = $state(5)
  let interval = $state(2)
  let raw = $state(false)
  let error = $state<string | null>(null)

  const seq = $derived($live?.sequence)
  const active = $derived(seq?.active ?? false)
  const pct = $derived(seq && seq.count ? (seq.done / seq.count) * 100 : 0)

  // Refresh the gallery as each frame completes.
  let prevDone = 0
  $effect(() => {
    const done = $live?.sequence?.done ?? 0
    if (done !== prevDone) {
      prevDone = done
      if (done > 0) bumpCaptures()
    }
  })

  async function start() {
    error = null
    try {
      await startSequence({ count, interval_s: interval, raw })
    } catch {
      error = 'could not start'
    }
  }
</script>

<section class="seq">
  <div class="head">
    <span class="label">Sequence</span>
    {#if active && seq}<span class="badge">running</span>{/if}
  </div>

  {#if active && seq}
    <div class="prow">
      <span>Frame {seq.done} / {seq.count}</span>
      <button class="cancel" onclick={cancelSequence}>Cancel</button>
    </div>
    <div class="track"><div class="fill" style:width="{pct}%"></div></div>
  {:else}
    <div class="fields">
      <label>
        Frames
        <input type="number" min="1" max="999" bind:value={count} />
      </label>
      <label>
        Interval (s)
        <input type="number" min="0" step="0.5" bind:value={interval} />
      </label>
      <label class="raw">
        <input type="checkbox" bind:checked={raw} />
        Raw
      </label>
    </div>
    <button class="start" onclick={start}>Start sequence</button>
  {/if}
  {#if error}<span class="err">{error}</span>{/if}
</section>

<style>
  .seq {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .badge {
    font-size: 0.72rem;
    color: var(--accent);
  }
  .fields {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    align-items: flex-end;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.78rem;
    color: var(--muted);
  }
  input[type='number'] {
    width: 5rem;
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.5rem;
    font-size: 0.9rem;
  }
  .raw {
    flex-direction: row;
    align-items: center;
    gap: 0.35rem;
  }
  .raw input {
    accent-color: var(--accent);
  }
  .start {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 0.5rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .prow {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
  }
  .cancel {
    background: transparent;
    color: var(--accent);
    border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
    border-radius: 8px;
    padding: 0.3rem 0.7rem;
    font-size: 0.82rem;
    cursor: pointer;
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
    transition: width 0.2s linear;
  }
  .err {
    color: var(--accent);
    font-size: 0.8rem;
  }
</style>
