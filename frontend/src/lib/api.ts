export type Control = { min: number; max: number; default: number }

export type CameraProfile = {
  model: string
  resolution: [number, number]
  max_resolution: [number, number]
  exposure_us: Control
  gain: Control
  supports_raw: boolean
  is_mock: boolean
}

export type SystemInfo = {
  camera: string
  mock: boolean
  state: string
  profile: CameraProfile
}

export async function getSystem(): Promise<SystemInfo> {
  const r = await fetch('/api/system')
  return r.json()
}

export async function getSettings(): Promise<{ profile: CameraProfile; controls: Record<string, number> }> {
  const r = await fetch('/api/camera/settings')
  return r.json()
}

export async function patchSettings(values: Record<string, number>): Promise<{ controls: Record<string, number> }> {
  const r = await fetch('/api/camera/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
  return r.json()
}

export type Roi = [number, number, number, number] | null

export async function setFocusRoi(roi: Roi): Promise<{ roi: Roi }> {
  const r = await fetch('/api/focus/roi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roi }),
  })
  return r.json()
}
