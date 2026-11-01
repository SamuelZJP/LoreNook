import { reactive, watch } from 'vue'
import type { Illustration, IllustrationMode } from './api'

export const MODE_LABELS: Record<IllustrationMode, string> = {
  off: '关闭',
  every_round: '每回合',
  scene_change: '场景变化时（地点或日期改变）',
  manual: '仅手动',
}

/** Beyond this, image models usually get noticeably worse. Only a warning. */
export const FOCUS_SOFT_LIMIT = 2

/** How many reference images a workflow receives; same as the backend. */
export const MAX_IMAGES = 8

const ACTIVE = ['pending', 'rendering']
export const isActive = (i: Illustration) => ACTIVE.includes(i.status)

export const mediaUrl = (name: string) => `/api/media/${name}`

/** Same placeholder rule as the backend. */
const PLACEHOLDER = /\{\{\s*((?:image:)?[A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g
const KNOWN = new Set(['prompt', 'images', 'seed', 'width', 'height'])
export function placeholders(workflow: unknown): { hasPrompt: boolean; unknown: string[] } {
  const names = new Set<string>()
  const walk = (v: unknown) => {
    if (typeof v === 'string') for (const m of v.matchAll(PLACEHOLDER)) names.add(m[1])
    else if (Array.isArray(v)) v.forEach(walk)
    else if (v && typeof v === 'object') Object.values(v).forEach(walk)
  }
  walk(workflow)
  return { hasPrompt: names.has('prompt'), unknown: [...names].filter((n) => !KNOWN.has(n)).sort() }
}

/** The round summary starts with a date—time—place header; it doubles as the plate caption. */
export function splitSummary(summary: string | null | undefined): { caption: string; body: string } {
  const text = (summary ?? '').trim()
  const [first, ...rest] = text.split('\n')
  if (!/^\d{2}/.test(first ?? '')) return { caption: '', body: text }
  const parts = first.split(/\s*[—–]+\s*/).filter(Boolean)
  // A header may run straight into narration on the same line; keep only short leading parts.
  if (parts.length < 2 || parts.slice(0, 3).some((p) => p.length > 24)) return { caption: '', body: text }
  return { caption: parts.slice(0, 3).join(' · '), body: [parts.slice(3).join('—'), ...rest].join('\n').trim() }
}

// ---- Preferences: this browser only, like the app's own prefs ----

const KEY = 'lorenook.illustrations'
type Backdrop = 'off' | 'subtle' | 'strong'
function load(): { backdrop: Backdrop } {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    return { backdrop: ['off', 'subtle', 'strong'].includes(stored.backdrop) ? stored.backdrop : 'subtle' }
  } catch {
    return { backdrop: 'subtle' }
  }
}
export const illustrationPrefs = reactive(load())
watch(illustrationPrefs, () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(illustrationPrefs))
  } catch {
    /* storage unavailable: keep in-memory prefs */
  }
})
