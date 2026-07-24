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

/** High-level, sensor-agnostic camera settings — mirrors the backend CameraSettings dataclass. */
export type CameraSettings = {
  ae_enable: boolean
  awb_enable: boolean
  exposure_us: number
  gain: number
  preview_mode: PreviewMode
}

export type PreviewMode = 'normal' | 'star'

// Single fetch wrapper: throws on a non-2xx response so callers can't mistake a backend error for a
// success payload (which would assign `undefined` into component state and wedge the UI).
async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) throw new Error(`${init?.method ?? 'GET'} ${url} → ${r.status}`)
  return r.json() as Promise<T>
}

function postJson<T>(url: string, body?: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
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
  power_controls: boolean
}

export function getSystem(): Promise<SystemInfo> {
  return fetchJson<SystemInfo>('/api/system')
}

export function powerHost(action: 'shutdown' | 'reboot'): Promise<{ action: string }> {
  return postJson('/api/system/power', { action })
}

export function startSequence(opts: {
  count: number
  interval_s: number
  exposure_us?: number
  raw?: boolean
  frame_type?: FrameType
}): Promise<unknown> {
  return postJson('/api/sequence', opts)
}

export async function cancelSequence(): Promise<void> {
  await postJson('/api/sequence/cancel')
}

export function getSettings(): Promise<{ profile: CameraProfile; settings: CameraSettings }> {
  return fetchJson('/api/camera/settings')
}

export async function patchSettings(
  values: Partial<CameraSettings>,
): Promise<{ settings: CameraSettings }> {
  return fetchJson('/api/camera/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
}

export type Preset = { name: string; settings: CameraSettings }

export async function listPresets(): Promise<Preset[]> {
  return (await fetchJson<{ presets: Preset[] }>('/api/camera/presets')).presets
}

export async function savePreset(name: string): Promise<Preset[]> {
  return (await postJson<{ presets: Preset[] }>('/api/camera/presets', { name })).presets
}

export function applyPreset(name: string): Promise<{ settings: CameraSettings }> {
  return postJson(`/api/camera/presets/${encodeURIComponent(name)}/apply`)
}

export async function deletePreset(name: string): Promise<Preset[]> {
  return (
    await fetchJson<{ presets: Preset[] }>(`/api/camera/presets/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
  ).presets
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
  jpeg_bytes: number | null
  raw_bytes: number | null
}

export type FrameType = 'light' | 'dark' | 'flat' | 'bias'

export function capture(
  opts: { raw?: boolean; exposure_us?: number; frame_type?: FrameType },
): Promise<Capture | { cancelled: true }> {
  return postJson('/api/capture', opts)
}

export async function cancelCapture(): Promise<void> {
  await postJson('/api/capture/cancel')
}

export async function listCaptures(): Promise<Capture[]> {
  return (await fetchJson<{ captures: Capture[] }>('/api/gallery')).captures
}

export async function deleteCapture(id: number): Promise<void> {
  await fetchJson(`/api/gallery/${id}`, { method: 'DELETE' })
}

export const thumbUrl = (id: number) => `/api/gallery/${id}/thumb`
export const imageUrl = (id: number) => `/api/gallery/${id}/image`
export const rawUrl = (id: number) => `/api/gallery/${id}/raw`

export type Roi = [number, number, number, number] | null

export function setFocusRoi(roi: Roi): Promise<{ roi: Roi }> {
  return postJson('/api/focus/roi', { roi })
}

export function setFocusMode(mode: FocusMode): Promise<{ mode: FocusMode }> {
  return postJson('/api/focus/mode', { mode })
}

/** Ask the sensor for a true 1:1 crop into the ROI (hardware only; mock returns hw_zoom=false). */
export function setFocusZoom(roi: Roi): Promise<{ roi: Roi; hw_zoom: boolean }> {
  return postJson('/api/focus/zoom', { roi })
}
