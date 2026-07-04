<script lang="ts">
  import { onMount } from 'svelte'
  import {
    getSettings,
    patchSettings,
    listPresets,
    savePreset,
    applyPreset,
    deletePreset,
    type CameraProfile,
    type CameraSettings,
    type Preset,
  } from '../lib/api'

  let profile = $state<CameraProfile | null>(null)
  let settings = $state<CameraSettings | null>(null)
  let presets = $state<Preset[]>([])
  let presetName = $state('')
  let busy = $state(false)

  onMount(async () => {
    const s = await getSettings()
    profile = s.profile
    settings = s.settings
    presets = await listPresets()
  })

  // --- exposure slider maps linearly in log space (100 µs … ~12 s is 5 decades) ---
  const logMin = $derived(profile ? Math.log10(profile.exposure_us.min) : 2)
  const logMax = $derived(profile ? Math.log10(profile.exposure_us.max) : 7)
  const expSlider = $derived(
    settings ? (Math.log10(settings.exposure_us) - logMin) / (logMax - logMin) : 0,
  )

  function fmtExposure(us: number): string {
    if (us >= 1_000_000) return `${(us / 1_000_000).toFixed(2)} s`
    if (us >= 1000) return `${(us / 1000).toFixed(0)} ms`
    return `${Math.round(us)} µs`
  }

  async function apply(update: Partial<CameraSettings>) {
    busy = true
    try {
      const r = await patchSettings(update)
      settings = r.settings
    } finally {
      busy = false
    }
  }

  const expFromFrac = (frac: number) => Math.round(10 ** (logMin + frac * (logMax - logMin)))

  // While dragging, only echo the value locally (moves the slider + label); the PATCH fires once
  // on release (change), so a drag is one request instead of ~30–60 hammering the driver.
  function onExposureInput(e: Event) {
    if (settings) settings = { ...settings, exposure_us: expFromFrac(Number((e.target as HTMLInputElement).value)) }
  }
  function onExposureCommit(e: Event) {
    apply({ exposure_us: expFromFrac(Number((e.target as HTMLInputElement).value)) })
  }
  function onGainInput(e: Event) {
    if (settings) settings = { ...settings, gain: Number((e.target as HTMLInputElement).value) }
  }
  function onGainCommit(e: Event) {
    apply({ gain: Number((e.target as HTMLInputElement).value) })
  }

  async function onSave() {
    const name = presetName.trim()
    if (!name) return
    presets = await savePreset(name)
    presetName = ''
  }

  async function onApplyPreset(name: string) {
    busy = true
    try {
      settings = (await applyPreset(name)).settings
    } finally {
      busy = false
    }
  }

  async function onDeletePreset(name: string) {
    presets = await deletePreset(name)
  }
</script>

<section class="controls" class:busy>
  {#if profile && settings}
    <div class="head">
      <span class="label">Camera controls</span>
      {#if settings.preview_mode === 'star'}
        <span class="tag">star preview · ~1 fps</span>
      {/if}
    </div>

    <div class="modes">
      <button class:active={settings.preview_mode === 'normal'} onclick={() => apply({ preview_mode: 'normal' })}>
        Normal
      </button>
      <button class:active={settings.preview_mode === 'star'} onclick={() => apply({ preview_mode: 'star' })}>
        Star
      </button>
    </div>
    {#if settings.preview_mode === 'star'}
      <p class="hint">Long-exposure preview so faint stars become visible — the stream slows to ~1 fps.</p>
    {/if}

    <label class="check">
      <input type="checkbox" checked={settings.ae_enable} onchange={(e) => apply({ ae_enable: (e.target as HTMLInputElement).checked })} />
      Auto exposure (AE)
    </label>
    <label class="check">
      <input type="checkbox" checked={settings.awb_enable} onchange={(e) => apply({ awb_enable: (e.target as HTMLInputElement).checked })} />
      Auto white balance (AWB)
    </label>

    <div class="slider" class:disabled={settings.ae_enable}>
      <div class="srow">
        <span>Exposure</span>
        <span class="val">{fmtExposure(settings.exposure_us)}</span>
      </div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.001"
        value={expSlider}
        disabled={settings.ae_enable}
        oninput={onExposureInput}
        onchange={onExposureCommit}
      />
    </div>

    <div class="slider" class:disabled={settings.ae_enable}>
      <div class="srow">
        <span>Gain (ISO)</span>
        <span class="val">{settings.gain.toFixed(1)}×</span>
      </div>
      <input
        type="range"
        min={profile.gain.min}
        max={profile.gain.max}
        step="0.1"
        value={settings.gain}
        disabled={settings.ae_enable}
        oninput={onGainInput}
        onchange={onGainCommit}
      />
    </div>

    <div class="presets">
      <div class="srow"><span>Presets</span></div>
      {#if presets.length}
        <ul>
          {#each presets as p (p.name)}
            <li>
              <button class="apply" onclick={() => onApplyPreset(p.name)}>{p.name}</button>
              <button class="del" title="delete" onclick={() => onDeletePreset(p.name)}>✕</button>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="hint">No presets yet — save the current settings below.</p>
      {/if}
      <div class="save">
        <input
          type="text"
          placeholder="name (e.g. Moon)"
          bind:value={presetName}
          onkeydown={(e) => e.key === 'Enter' && onSave()}
        />
        <button onclick={onSave} disabled={!presetName.trim()}>Save</button>
      </div>
    </div>
  {:else}
    <p class="hint">Loading controls…</p>
  {/if}
</section>

<style>
  .controls {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .controls.busy {
    opacity: 0.85;
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
  .tag {
    font-size: 0.72rem;
    color: var(--accent);
  }
  .modes {
    display: flex;
    gap: 0.4rem;
  }
  .modes button {
    flex: 1;
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.4rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .modes button.active {
    border-color: var(--accent);
    color: var(--accent);
    box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 40%, transparent);
  }
  .check {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
  }
  .check input {
    accent-color: var(--accent);
  }
  .slider.disabled {
    opacity: 0.45;
  }
  .srow {
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    color: var(--muted);
    margin-bottom: 0.2rem;
  }
  .val {
    color: var(--fg);
    font-variant-numeric: tabular-nums;
  }
  input[type='range'] {
    width: 100%;
    accent-color: var(--accent);
  }
  .presets ul {
    list-style: none;
    margin: 0.3rem 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .presets li {
    display: flex;
    align-items: stretch;
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
  }
  .presets .apply {
    background: transparent;
    color: var(--fg);
    border: none;
    padding: 0.3rem 0.55rem;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .presets .del {
    background: transparent;
    color: var(--muted);
    border: none;
    border-left: 1px solid var(--line);
    padding: 0 0.5rem;
    cursor: pointer;
  }
  .presets .del:hover {
    color: var(--accent);
  }
  .save {
    display: flex;
    gap: 0.4rem;
  }
  .save input {
    flex: 1;
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.5rem;
    font-size: 0.85rem;
  }
  .save button {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.35rem 0.7rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .save button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .hint {
    color: var(--muted);
    font-size: 0.72rem;
    margin: 0;
  }
</style>
