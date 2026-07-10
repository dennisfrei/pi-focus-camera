<script lang="ts">
  import { onMount } from 'svelte'
  import { live, connected } from '../lib/live'
  import { getSystem, powerHost, type SystemInfo } from '../lib/api'
  import { formatBytes } from '../lib/format'

  let system = $state<SystemInfo | null>(null)

  async function power(action: 'shutdown' | 'reboot') {
    if (!confirm(`${action === 'shutdown' ? 'Shut down' : 'Reboot'} the camera now?`)) return
    await powerHost(action).catch(() => {})
  }

  onMount(() => {
    const load = () =>
      getSystem()
        .then((s) => (system = s))
        .catch(() => {})
    load()
    const timer = setInterval(load, 5000) // temp/disk drift slowly; 5 s is plenty
    return () => clearInterval(timer)
  })

  // Field warnings: the Pi soft-throttles around 80 °C, and raw subs fill a disk fast.
  const TEMP_WARN_C = 75
  const DISK_WARN_BYTES = 1024 ** 3 // 1 GB
  const tempWarn = $derived(system?.cpu_temp_c != null && system.cpu_temp_c > TEMP_WARN_C)
  const diskWarn = $derived(system != null && system.disk.free < DISK_WARN_BYTES)

  function fmtUptime(s: number | null): string {
    if (s == null) return '—'
    const d = Math.floor(s / 86400)
    const h = Math.floor((s % 86400) / 3600)
    const m = Math.floor((s % 3600) / 60)
    return d > 0 ? `${d}d ${h}h ${m}m` : h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  // The raw `state` is just idle/preview — surface what the camera is actually doing right now.
  const activity = $derived.by(() => {
    const l = $live
    if (!l) return '—'
    if (l.capture?.active) return 'capturing…'
    if (l.sequence?.active) return `sequence ${l.sequence.done}/${l.sequence.count}`
    if (l.settings?.preview_mode === 'star') return 'star preview'
    return l.state ?? 'preview'
  })
</script>

<section class="status">
  <div class="row">
    <span class="label">Camera</span>
    <span class="value">{$live?.camera ?? system?.camera ?? '—'}</span>
  </div>
  <div class="row">
    <span class="label">State</span>
    <span class="value">{activity}</span>
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
      <span class="value" class:warn={tempWarn}>
        {system.cpu_temp_c != null ? `${system.cpu_temp_c} °C` : '—'}{tempWarn ? ' ⚠' : ''}
      </span>
    </div>
    <div class="row">
      <span class="label">Disk free</span>
      <span class="value" class:warn={diskWarn}>
        {formatBytes(system.disk.free)} / {formatBytes(system.disk.total)}{diskWarn ? ' ⚠' : ''}
      </span>
    </div>
    <div class="row">
      <span class="label">Uptime</span>
      <span class="value">{fmtUptime(system.uptime_s)}</span>
    </div>
    {#if system.mock}
      <div class="badge">MOCK CAMERA — no hardware</div>
    {/if}
    {#if system.power_controls}
      <div class="power">
        <button onclick={() => power('reboot')}>Reboot</button>
        <button class="danger" onclick={() => power('shutdown')}>Shut down</button>
      </div>
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
  .value.warn {
    color: var(--accent);
    font-weight: 600;
  }
  .power {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.7rem;
  }
  .power button {
    flex: 1;
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.4rem;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .power button.danger {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 50%, transparent);
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
