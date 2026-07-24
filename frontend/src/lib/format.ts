// Shared display formatters — one home for these so the capture bar, controls slider, gallery, and
// system panel can't drift apart (they had three copies of the exposure formatter and two of bytes).

export function formatBytes(n: number | null): string {
  if (n == null) return '—'
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  if (n >= 1024) return `${(n / 1024).toFixed(0)} kB`
  return `${n} B`
}

export function formatExposure(us: number): string {
  if (us >= 1_000_000) return `${(us / 1_000_000).toFixed(2)} s`
  if (us >= 1000) return `${(us / 1000).toFixed(0)} ms`
  return `${Math.round(us)} µs`
}
