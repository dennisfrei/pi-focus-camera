<script lang="ts">
  import { live } from '../lib/live'
  import { setFocusMode, type FocusMode } from '../lib/api'

  // Two metrics with opposite senses: Scene (Laplacian) you maximize, Star (HFD) you minimize.
  // The bar always means "fuller = better focus"; the sparkline shows the raw metric trend
  // (rising in Scene, dipping toward focus in Star — the classic HFD V-curve) so you can watch it
  // move as you turn the focuser. Both auto-scale to the recent window, since the metric's absolute
  // value is scene-dependent.
  const N = 120

  let mode = $state<FocusMode>('star')
  let metric = $state('HFD')
  let direction = $state<'higher' | 'lower'>('lower')
  let score = $state(0)
  let hfd = $state<number | null>(null)
  let peak = $state<number | null>(null)
  let starFound = $state<boolean | null>(null)

  let buffer: number[] = []
  let prevMode: FocusMode | null = null
  let pct = $state(0)
  let points = $state('')

  const noStar = $derived(mode === 'star' && starFound === false)

  $effect(() => {
    const l = $live
    if (!l) return
    metric = l.focus_metric || metric
    direction = l.focus_direction
    hfd = l.hfd
    peak = l.peak
    starFound = l.star_found

    if (l.focus_mode !== prevMode) {
      buffer = [] // metric scale changes completely between modes — start the window fresh
      prevMode = l.focus_mode
      mode = l.focus_mode
    }

    const s = l.focus_score
    // Skip samples with no star to measure, so the meter doesn't read a misleading perfect focus.
    if (s == null || (l.focus_mode === 'star' && l.star_found === false)) return
    score = s
    buffer.push(s)
    if (buffer.length > N) buffer.shift()

    const lo = Math.min(...buffer)
    const hi = Math.max(...buffer)
    const span = hi - lo || 1
    pct = direction === 'lower' ? ((hi - s) / span) * 100 : ((s - lo) / span) * 100
    points = buffer
      .map((v, i) => `${(i / (N - 1)) * 100},${100 - ((v - lo) / span) * 100}`)
      .join(' ')
  })

  async function pick(m: FocusMode) {
    mode = m
    buffer = []
    await setFocusMode(m)
  }

  const displayScore = $derived(
    mode === 'star' ? (hfd ?? 0).toFixed(2) : Math.round(score).toString(),
  )
</script>

<div class="meter">
  <div class="head">
    <span class="label">Focus</span>
    <div class="modes">
      <button class:active={mode === 'scene'} onclick={() => pick('scene')}>Scene</button>
      <button class:active={mode === 'star'} onclick={() => pick('star')}>Star</button>
    </div>
  </div>

  <div class="readout">
    <span class="score">{noStar ? '—' : displayScore}</span>
    <span class="unit">{metric}{mode === 'star' ? ' px' : ''}</span>
    {#if mode === 'star' && !noStar && peak != null}
      <span class="peak">peak {peak}</span>
    {/if}
  </div>

  <div class="bar"><div class="fill" style:width="{noStar ? 0 : pct}%"></div></div>
  <svg class="spark" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    <polyline {points} />
  </svg>

  {#if noStar}
    <p class="hint warn">no star in the region — drag a box over a bright star</p>
  {:else}
    <p class="hint">
      {mode === 'star'
        ? 'turn the focuser to minimize HFD — tighter star, smaller number'
        : 'turn the focuser to maximize sharpness — crisper image, higher score'}
    </p>
  {/if}
</div>

<style>
  .meter {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .modes {
    display: flex;
    gap: 0.3rem;
  }
  .modes button {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: 7px;
    padding: 0.15rem 0.5rem;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .modes button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .readout {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    margin: 0.2rem 0;
  }
  .score {
    font-size: 1.8rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .unit {
    color: var(--muted);
    font-size: 0.8rem;
  }
  .peak {
    margin-left: auto;
    color: var(--muted);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }
  .bar {
    height: 10px;
    background: color-mix(in srgb, var(--line) 60%, transparent);
    border-radius: 6px;
    overflow: hidden;
    margin: 0.4rem 0;
  }
  .fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.1s linear;
  }
  .spark {
    width: 100%;
    height: 44px;
    display: block;
  }
  .spark polyline {
    fill: none;
    stroke: var(--accent);
    stroke-width: 1.5;
    vector-effect: non-scaling-stroke;
  }
  .hint {
    color: var(--muted);
    font-size: 0.72rem;
    margin: 0.3rem 0 0;
  }
  .hint.warn {
    color: var(--accent);
  }
</style>
