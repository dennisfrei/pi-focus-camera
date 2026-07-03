import { writable } from 'svelte/store'
import type { CameraSettings } from './api'

export type LiveState = {
  state: string
  camera: string
  mock: boolean
  focus_score: number
  histogram: number[]
  clipping: number
  roi: [number, number, number, number] | null
  settings: CameraSettings
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
