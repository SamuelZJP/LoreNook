export function formatTime(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function initials(name: string | null | undefined): string {
  const trimmed = (name ?? '').trim()
  return trimmed ? Array.from(trimmed)[0].toUpperCase() : '?'
}

/** Stable hue from a string, for avatar fallbacks. */
export function hue(seed: string): number {
  let h = 0
  for (const ch of seed) h = (h * 31 + ch.codePointAt(0)!) % 360
  return h
}

/** Same {{user}} / {{char}} replacement the backend applies before the preset runs. */
export function substituteNames(text: string, user: string, char: string): string {
  return text.replace(/\{\{\s*(user|char)\s*\}\}/gi, (_, key: string) => (key.toLowerCase() === 'user' ? user : char))
}

export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2)
}
