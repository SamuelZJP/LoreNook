import type { Component } from 'vue'
import { Cpu, Feather, Image, LayoutTemplate, Drama, UserRound } from 'lucide-vue-next'

/** The kinds of library records, in the order the hub shows them. */
export type LibraryKind = 'characters' | 'identities' | 'presets' | 'models' | 'workflows' | 'templates'

export interface KindInfo {
  id: LibraryKind
  label: string
  /** Used in "新建…" and the editor title. */
  noun: string
  icon: Component
  /** Profiles are the people of a story; settings are how the AI works. */
  group: 'profiles' | 'settings'
  /** Short line under a hub tile. */
  blurb: string
}

export const KINDS: KindInfo[] = [
  { id: 'characters', label: '角色', noun: '角色', icon: Drama, group: 'profiles', blurb: '故事里的人' },
  { id: 'identities', label: '我的身份', noun: '身份', icon: UserRound, group: 'profiles', blurb: '你在故事里的样子' },
  { id: 'presets', label: '写作风格', noun: '写作风格', icon: Feather, group: 'settings', blurb: '决定怎么写' },
  { id: 'models', label: '模型', noun: '模型', icon: Cpu, group: 'settings', blurb: '由谁来写' },
  { id: 'workflows', label: '绘图', noun: '绘图工作流', icon: Image, group: 'settings', blurb: '插图从哪来' },
  { id: 'templates', label: '开局模板', noun: '开局模板', icon: LayoutTemplate, group: 'settings', blurb: '新聊天的默认设置' },
]

export const kindInfo = (id: LibraryKind) => KINDS.find((k) => k.id === id)!
