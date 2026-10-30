import { computed, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api, type Illustration, type IllustrationMode, type RoundRead } from '@/api/endpoints'

export const MODE_LABELS: Record<IllustrationMode, string> = {
  off: '关闭',
  every_round: '每回合',
  scene_change: '场景变化时（地点或日期改变）',
  manual: '仅手动',
}

export const ACTIVE = ['pending', 'prompting', 'rendering'] as const
export const isActive = (i: Illustration) => (ACTIVE as readonly string[]).includes(i.status)

/** Same placeholder rule as the backend; `seed`, `width`, `height` are filled by LoreNook. */
const PLACEHOLDER = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g
const BUILTINS = new Set(['seed', 'width', 'height'])
export function promptFields(workflow: unknown): string[] {
  const names = new Set<string>()
  const walk = (v: unknown) => {
    if (typeof v === 'string') for (const m of v.matchAll(PLACEHOLDER)) names.add(m[1])
    else if (Array.isArray(v)) v.forEach(walk)
    else if (v && typeof v === 'object') Object.values(v).forEach(walk)
  }
  walk(workflow)
  return [...names].filter((n) => !BUILTINS.has(n)).sort()
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

/** A chat's illustrations, polled while any job runs. The newest attempt per round is the one shown. */
export function useIllustrations(chatId: Ref<string>) {
  const query = useQuery({
    queryKey: computed(() => ['illustrations', chatId.value]),
    queryFn: () => api.illustrations(chatId.value),
    refetchInterval: (q) => ((q.state.data ?? []).some(isActive) ? 2000 : false),
  })
  const byRound = computed(() => {
    const map = new Map<string, Illustration>()
    for (const item of query.data.value ?? []) map.set(item.round_id, item) // ordered oldest first
    return map
  })
  return { query, byRound }
}

/** Ready, visible illustrations in round order, for the scene viewer and backdrop. */
export function gallery(rounds: RoundRead[], byRound: Map<string, Illustration>) {
  return rounds.flatMap((round) => {
    const item = byRound.get(round.id)
    return item && item.status === 'ready' && !item.hidden ? [{ round, illustration: item }] : []
  })
}
