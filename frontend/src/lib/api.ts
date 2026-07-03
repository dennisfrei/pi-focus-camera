export type Control = { min: number; max: number; default: number }

export type CameraProfile = {
  model: string
  resolution: [number, number]
  max_resolution: [number, number]
  exposure_us: Control
  gain: Control
  supports_raw: boolean
  is_mock: boolean
  supports_hw_zoom: boolean
}

export type FocusMode = 'scene' | 'star'

export type PreviewMode = 'normal' | 'star'

/** High-level, sensor-agnostic camera settings — mirrors the backend CameraSettings dataclass. */
export type CameraSettings = {
  ae_enable: boolean
  awb_enable: boolean
  exposure_us: number
  gain: number
  preview_mode: PreviewMode
}

export type DiskUsage = { total: number; used: number; free: number }

export type SystemInfo = {
  camera: string
  mock: boolean
  state: string
  profile: CameraProfile
  cpu_temp_c: number | null
  uptime_s: number | null
  disk: DiskUsage
}

export async function getSystem(): Promise<SystemInfo> {
  const r = await fetch('/api/system')
  return r.json()
}

export async function startSequence(opts: {
  count: number
  interval_s: number
  exposure_us?: number
  raw?: boolean
}): Promise<unknown> {
  const r = await fetch('/api/sequence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  if (!r.ok) throw new Error('sequence rejected')
  return r.json()
}

export async function cancelSequence(): Promise<void> {
  await fetch('/api/sequence/cancel', { method: 'POST' })
}

export async function getSettings(): Promise<{ profile: CameraProfile; settings: CameraSettings }> {
  const r = await fetch('/api/camera/settings')
  return r.json()
}

export async function patchSettings(
  values: Partial<CameraSettings>,
): Promise<{ settings: CameraSettings }> {
  const r = await fetch('/api/camera/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
  return r.json()
}

export type Preset = { name: string; settings: CameraSettings }

export async function listPresets(): Promise<Preset[]> {
  const r = await fetch('/api/camera/presets')
  return (await r.json()).presets
}

export async function savePreset(name: string): Promise<Preset[]> {
  const r = await fetch('/api/camera/presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return (await r.json()).presets
}

export async function applyPreset(name: string): Promise<{ settings: CameraSettings }> {
  const r = await fetch(`/api/camera/presets/${encodeURIComponent(name)}/apply`, { method: 'POST' })
  return r.json()
}

export async function deletePreset(name: string): Promise<Preset[]> {
  const r = await fetch(`/api/camera/presets/${encodeURIComponent(name)}`, { method: 'DELETE' })
  return (await r.json()).presets
}

export type Capture = {
  id: number
  created: number
  settings: Record<string, number | boolean | string>
  width: number
  height: number
  jpeg_path: string
  raw_path: string | null
  thumb_path: string
  has_raw: boolean
}

export async function capture(opts: { raw?: boolean; exposure_us?: number }): Promise<Capture> {
  const r = await fetch('/api/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  return r.json()
}

export async function listCaptures(): Promise<Capture[]> {
  const r = await fetch('/api/gallery')
  return (await r.json()).captures
}

export async function deleteCapture(id: number): Promise<void> {
  await fetch(`/api/gallery/${id}`, { method: 'DELETE' })
}

export const thumbUrl = (id: number) => `/api/gallery/${id}/thumb`
export const imageUrl = (id: number) => `/api/gallery/${id}/image`
export const rawUrl = (id: number) => `/api/gallery/${id}/raw`

export type Roi = [number, number, number, number] | null

export async function setFocusRoi(roi: Roi): Promise<{ roi: Roi }> {
  const r = await fetch('/api/focus/roi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roi }),
  })
  return r.json()
}

export async function setFocusMode(mode: FocusMode): Promise<{ mode: FocusMode }> {
  const r = await fetch('/api/focus/mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  return r.json()
}

/** Ask the sensor for a true 1:1 crop into the ROI (hardware only; mock returns hw_zoom=false). */
export async function setFocusZoom(roi: Roi): Promise<{ roi: Roi; hw_zoom: boolean }> {
  const r = await fetch('/api/focus/zoom', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roi }),
  })
  return r.json()
}
