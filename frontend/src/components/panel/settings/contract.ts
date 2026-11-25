import type { Component } from 'vue'

/**
 * How an optional feature joins a chat's settings. Every component receives
 * `{ chat: ChatDetail }` and saves through `useSaveTracker()`.
 */
export type CorePage = 'writing' | 'memory' | 'archive'

/** Its own row in the list: an inline control when there is no page. */
export interface SettingsRow {
  id: string
  label: string
  icon: Component
  order: number
  Summary: Component
  Page?: Component
}

/** A block inside one of the core pages, with an optional addition to that page's summary. */
export interface SettingsBlock {
  page: CorePage
  order: number
  Block: Component
  Summary?: Component
}

export interface ChatSettingsContribution {
  rows?: SettingsRow[]
  blocks?: SettingsBlock[]
}
