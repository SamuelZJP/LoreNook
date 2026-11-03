import { reactive, watch } from 'vue'
import { EN_FONTS, ZH_FONTS, readingFonts, type EnFont, type ZhFont } from './fonts'

/**
 * Frontend-only preferences, stored in this browser's localStorage. They do not sync across
 * browsers or devices and are not part of the backend data.
 */
export type SectionMode = 'show' | 'collapse' | 'hide'
/** Decides how a section looks; `SectionMode` separately decides whether it is visible. */
export type RenderCategory = 'thought' | 'prose' | 'other'

export interface SectionRule {
  category: RenderCategory
  mode: SectionMode
}

/** Mode preselected when a tag is added with a given category. */
export const categoryDefaultMode: Record<RenderCategory, SectionMode> = {
  thought: 'collapse',
  prose: 'show',
  other: 'collapse',
}

export interface Prefs {
  theme: 'system' | 'light' | 'dark'
  fontSize: number
  zhFont: ZhFont
  enFont: EnFont
  markdown: boolean
  sendKey: 'ctrl-enter' | 'enter'
  showFloorNumbers: boolean
  showSummaries: boolean
  /** Most recent floors rendered in a chat; `null` renders all. Display only. */
  floorLimit: number | null
  /** Reply bubble height limit, in % of the chat area; the body scrolls inside. `null` turns it off. */
  replyCap: number | null
  /** Data management: list round-ordered rows newest first. */
  dataNewestFirst: boolean
  /** Stored-format version; see `load`. */
  version: number
  /** Rendering rule per tag name; tags not listed use `unknownSection`. */
  sections: Record<string, SectionRule>
  unknownSection: SectionRule
  /** How text outside any tag is rendered. */
  looseText: SectionRule
}

const KEY = 'lorenook.prefs'
const VERSION = 2

const defaults: Prefs = {
  theme: 'system',
  fontSize: 16,
  zhFont: 'noto-serif',
  enFont: 'follow',
  markdown: true,
  sendKey: 'ctrl-enter',
  showFloorNumbers: true,
  showSummaries: false,
  floorLimit: 100,
  replyCap: 100,
  dataNewestFirst: true,
  version: VERSION,
  sections: {
    content: { category: 'prose', mode: 'show' },
    think: { category: 'thought', mode: 'collapse' },
  },
  unknownSection: { category: 'other', mode: 'collapse' },
  looseText: { category: 'other', mode: 'collapse' },
}

const MODES: SectionMode[] = ['show', 'collapse', 'hide']
const CATEGORIES: RenderCategory[] = ['thought', 'prose', 'other']

/** Accepts current rules and the earlier mode-only strings. */
function toRule(value: unknown, fallback: SectionRule, legacyCategory: RenderCategory): SectionRule {
  if (typeof value === 'string') {
    return MODES.includes(value as SectionMode) ? { category: legacyCategory, mode: value as SectionMode } : { ...fallback }
  }
  const v = (value ?? {}) as Partial<SectionRule>
  return {
    category: CATEGORIES.includes(v.category as RenderCategory) ? (v.category as RenderCategory) : fallback.category,
    mode: MODES.includes(v.mode as SectionMode) ? (v.mode as SectionMode) : fallback.mode,
  }
}

function toFloorLimit(value: unknown): number | null {
  if (value === null) return null
  return Number.isInteger(value) && (value as number) > 0 ? (value as number) : defaults.floorLimit
}

export const REPLY_CAP_RANGE = { min: 30, max: 300 }
function toReplyCap(value: unknown): number | null {
  if (value === null) return null
  const ok = Number.isInteger(value) && (value as number) >= REPLY_CAP_RANGE.min && (value as number) <= REPLY_CAP_RANGE.max
  return ok ? (value as number) : defaults.replyCap
}

function load(): Prefs {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    // Version 1 saved every field on any change, so a stored `showSummaries: true` is
    // indistinguishable from the old default; drop it so the new collapsed default applies.
    if ((stored.version ?? 1) < 2 && stored.showSummaries === true) delete stored.showSummaries
    const sections: Record<string, SectionRule> = structuredClone(defaults.sections)
    for (const [name, value] of Object.entries(stored.sections ?? {})) {
      const fallback = defaults.sections[name] ?? defaults.unknownSection
      sections[name] = toRule(value, fallback, fallback.category)
    }
    return {
      ...structuredClone(defaults),
      ...stored,
      sections,
      unknownSection: toRule(stored.unknownSection, defaults.unknownSection, 'other'),
      looseText: toRule(stored.looseText, defaults.looseText, 'other'),
      zhFont: ZH_FONTS.some((f) => f.id === stored.zhFont) ? stored.zhFont : defaults.zhFont,
      enFont: EN_FONTS.some((f) => f.id === stored.enFont) ? stored.enFont : defaults.enFont,
      floorLimit: toFloorLimit(stored.floorLimit),
      replyCap: toReplyCap(stored.replyCap),
      version: VERSION,
    }
  } catch {
    return structuredClone(defaults)
  }
}

export const prefs = reactive<Prefs>(load())

export function resetPrefs() {
  Object.assign(prefs, structuredClone(defaults))
}

export function sectionRule(name: string): SectionRule {
  return prefs.sections[name] ?? prefs.unknownSection
}

function apply() {
  const root = document.documentElement
  if (prefs.theme === 'system') delete root.dataset.theme
  else root.dataset.theme = prefs.theme
  root.style.setProperty('--reading-size', `${prefs.fontSize}px`)
  const fonts = readingFonts(prefs.zhFont, prefs.enFont)
  root.style.setProperty('--font-reading', fonts.reading)
  root.style.setProperty('--font-thought', fonts.thought)
}

watch(
  prefs,
  () => {
    try {
      localStorage.setItem(KEY, JSON.stringify(prefs))
    } catch {
      /* storage unavailable: keep in-memory prefs */
    }
    apply()
  },
  { deep: true },
)
apply()
