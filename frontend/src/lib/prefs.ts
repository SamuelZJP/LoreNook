import { reactive, watch } from 'vue'

/**
 * Frontend-only preferences, stored in this browser's localStorage. They do not sync across
 * browsers or devices and are not part of the backend data.
 */
export type SectionMode = 'show' | 'collapse' | 'hide'

export interface Prefs {
  theme: 'system' | 'light' | 'dark'
  fontSize: number
  markdown: boolean
  sendKey: 'ctrl-enter' | 'enter'
  showFloorNumbers: boolean
  showSummaries: boolean
  /** Display mode per tag name; tags not listed use `unknownSection`. */
  sections: Record<string, SectionMode>
  unknownSection: SectionMode
  /** How text outside any tag is shown. */
  looseText: SectionMode
}

const KEY = 'lorenook.prefs'

const defaults: Prefs = {
  theme: 'system',
  fontSize: 16,
  markdown: true,
  sendKey: 'ctrl-enter',
  showFloorNumbers: true,
  showSummaries: true,
  sections: { content: 'show', think: 'collapse' },
  unknownSection: 'collapse',
  looseText: 'collapse',
}

function load(): Prefs {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    return { ...defaults, ...stored, sections: { ...defaults.sections, ...(stored.sections ?? {}) } }
  } catch {
    return structuredClone(defaults)
  }
}

export const prefs = reactive<Prefs>(load())

export function resetPrefs() {
  Object.assign(prefs, structuredClone(defaults))
}

export function sectionMode(name: string): SectionMode {
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
