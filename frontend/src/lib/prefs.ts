import { reactive, watch } from 'vue'

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
  markdown: boolean
  sendKey: 'ctrl-enter' | 'enter'
  showFloorNumbers: boolean
  showSummaries: boolean
  /** Rendering rule per tag name; tags not listed use `unknownSection`. */
  sections: Record<string, SectionRule>
  unknownSection: SectionRule
  /** How text outside any tag is rendered. */
  looseText: SectionRule
}

const KEY = 'lorenook.prefs'

const defaults: Prefs = {
  theme: 'system',
  fontSize: 16,
  markdown: true,
  sendKey: 'ctrl-enter',
  showFloorNumbers: true,
  showSummaries: true,
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

function load(): Prefs {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) ?? '{}')
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
