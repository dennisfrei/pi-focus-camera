import { writable } from 'svelte/store'
import type { CameraSettings, FocusMode } from './api'

export type CaptureState = {
  active: boolean
  progress: number
  remaining_s: number
  exposure_us: number
  raw: boolean
}

export type LiveState = {
  state: string
  camera: string
  mock: boolean
  focus_score: number
  focus_mode: FocusMode
  focus_metric: string
  focus_direction: 'higher' | 'lower'
  hfd: number | null
  peak: number | null
  star_found: boolean | null
  histogram: number[]
  clipping: number
  roi: [number, number, number, number] | null
  settings: CameraSettings
  capture: CaptureState
} | null

export const live = writable<LiveState>(null)
export const connected = writable(false)

/** Connect to /api/live and keep it alive with auto-reconnect. */
export function connectLive(): void {
  const url = `${location.origin.replace(/^http/, 'ws')}/api/live`
  let ws: WebSocket

  const open = () => {
    ws = new WebSocket(url)
    ws.onopen = () => connected.set(true)
    ws.onmessage = (e) => live.set(JSON.parse(e.data))
    ws.onclose = () => {
      connected.set(false)
      setTimeout(open, 1000)
    }
    ws.onerror = () => ws.close()
  }
  open()
}
