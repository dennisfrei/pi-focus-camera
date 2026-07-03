<script lang="ts">
  import { onMount } from 'svelte'
  import { live, connected } from '../lib/live'
  import { getSystem, type SystemInfo } from '../lib/api'

  let system = $state<SystemInfo | null>(null)

  onMount(() => {
    const load = () =>
      getSystem()
        .then((s) => (system = s))
        .catch(() => {})
    load()
    const timer = setInterval(load, 5000) // temp/disk drift slowly; 5 s is plenty
    return () => clearInterval(timer)
  })

  const gb = (bytes: number) => (bytes / 1024 ** 3).toFixed(1)

  function fmtUptime(s: number | null): string {
    if (s == null) return '—'
    const d = Math.floor(s / 86400)
    const h = Math.floor((s % 86400) / 3600)
    const m = Math.floor((s % 3600) / 60)
    return d > 0 ? `${d}d ${h}h ${m}m` : h > 0 ? `${h}h ${m}m` : `${m}m`
  }
</script>

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
    <div class="row">
      <span class="label">CPU temp</span>
      <span class="value">{system.cpu_temp_c != null ? `${system.cpu_temp_c} °C` : '—'}</span>
    </div>
    <div class="row">
      <span class="label">Disk free</span>
      <span class="value">{gb(system.disk.free)} / {gb(system.disk.total)} GB</span>
    </div>
    <div class="row">
      <span class="label">Uptime</span>
      <span class="value">{fmtUptime(system.uptime_s)}</span>
    </div>
    {#if system.mock}
      <div class="badge">MOCK CAMERA — no hardware</div>
    {/if}
  {/if}
</section>

<style>
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
