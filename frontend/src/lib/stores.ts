import { writable } from 'svelte/store'

/** Red-on-black night-vision theme — on by default (astronomy). */
export const nightMode = writable(true)

/** Screen dimmer (CSS brightness multiplier) to protect dark adaptation at the eyepiece. */
export const dimLevel = writable(1)

/** Bumped whenever the capture set changes (new capture / delete) so the gallery reloads. */
export const capturesChanged = writable(0)
export const bumpCaptures = () => capturesChanged.update((n) => n + 1)
