<script lang="ts">
  import { live } from '../lib/live'

  // The sharpness score is scene-dependent and unbounded, so we auto-scale against a slowly
  // decaying rolling maximum and let the user turn the focuser to push the bar toward 100 %.
  const N = 120 // history samples for the sparkline
  let buffer: number[] = []
  let rollingMax = 1

  let score = $state(0)
  let pct = $state(0)
  let points = $state('')

  $effect(() => {
    const s = $live?.focus_score
    if (s == null) return
    score = s
    buffer.push(s)
    if (buffer.length > N) buffer.shift()
    rollingMax = Math.max(rollingMax * 0.995, s, 1)
    pct = Math.min(100, (s / rollingMax) * 100)
    points = buffer
      .map((v, i) => `${(i / (N - 1)) * 100},${100 - Math.min(100, (v / rollingMax) * 100)}`)
      .join(' ')
  })
</script>

<div class="meter">
  <div class="head">
    <span class="label">Focus</span>
    <span class="score">{score.toFixed(0)}</span>
  </div>
  <div class="bar"><div class="fill" style:width="{pct}%"></div></div>
  <svg class="spark" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    <polyline {points} />
  </svg>
  <p class="hint">turn the focuser to maximize — sharper image, higher score</p>
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
    align-items: baseline;
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .score {
    font-size: 1.8rem;
    font-weight: 700;
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
</style>
