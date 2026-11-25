export function formatTime(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const SHORT_WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** Compact list time: today's clock, 昨天, a weekday within the week, else month/day (with year if not this year). */
export function formatShortTime(value: string | null | undefined, now = new Date()): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((day(now) - day(date)) / 86_400_000)
  if (days === 0) return `${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (days === 1) return '昨天'
  if (days > 1 && days < 7) return SHORT_WEEKDAYS[date.getDay()]
  const md = `${date.getMonth() + 1}/${date.getDate()}`
  return date.getFullYear() === now.getFullYear() ? md : `${date.getFullYear()}/${md}`
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

/** A round's `日期 · 时间 · 地点` line; empty parts are left out. */
export function sceneLine(scene: { date: string; time: string; place: string } | null | undefined): string {
  return scene ? [scene.date, scene.time, scene.place].filter(Boolean).join(' · ') : ''
}
