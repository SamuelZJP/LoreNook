import { computed, inject, provide, reactive, ref, watch, type InjectionKey, type Ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { RoundRead } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import { illustrationApi, type Illustration } from './api'
import { isActive, illustrationPrefs } from './lib'

/** The illustration state of one open chat, shared by the pieces placed inside the chat view. */
export function provideChatIllustrations(chatId: Ref<string>, rounds: Ref<RoundRead[]>) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: computed(() => ['illustrations', chatId.value]),
    queryFn: () => illustrationApi.illustrations(chatId.value),
    // Poll only while a job runs.
    refetchInterval: (q) => ((q.state.data ?? []).some(isActive) ? 2000 : false),
  })
  const settings = useQuery({
    queryKey: computed(() => ['illustration-settings', chatId.value]),
    queryFn: () => illustrationApi.settings(chatId.value),
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['illustrations', chatId.value] })

  // An archive that just completed may have queued a job.
  const latestArchived = computed(() => rounds.value.filter((r) => r.archive_step === 'complete').at(-1)?.id)
  watch(latestArchived, (now, before) => { if (before !== undefined || now !== undefined) refresh() })

  /** Newest attempt per round; the list is ordered oldest first. */
  const byRound = computed(() => {
    const map = new Map<string, Illustration>()
    for (const item of query.data.value ?? []) map.set(item.round_id, item)
    return map
  })
  const enabled = computed(() => (settings.data.value?.mode ?? 'off') !== 'off')
  /** Ready, visible illustrations in round order. */
  const gallery = computed(() => rounds.value.flatMap((round) => {
    const illustration = byRound.value.get(round.id)
    return illustration && illustration.status === 'ready' && !illustration.hidden ? [{ round, illustration }] : []
  }))
  const backdrop = computed(() => (illustrationPrefs.backdrop === 'off' ? null : gallery.value.at(-1)?.illustration ?? null))

  const viewing = ref<string | null>(null)
  const promptOf = ref<Illustration | null>(null)
  const choosingFocus = ref<string | null>(null)
  const requesting = reactive(new Set<string>())

  const report = (e: unknown) => toast(e instanceof Error ? e.message : String(e), 'error')
  async function illustrate(roundId: string, focus?: string[]) {
    if (requesting.has(roundId)) return
    requesting.add(roundId)
    try {
      await illustrationApi.illustrate(chatId.value, roundId, focus)
    } catch (e) {
      report(e)
    } finally {
      requesting.delete(roundId)
      refresh()
    }
  }
  async function setHidden(item: Illustration, hidden: boolean) {
    try {
      await illustrationApi.patchIllustration(chatId.value, item.id, { hidden })
    } catch (e) {
      report(e)
    } finally {
      refresh()
    }
  }
  const busy = (roundId: string) => {
    const item = byRound.value.get(roundId)
    return requesting.has(roundId) || (item ? isActive(item) : false)
  }
  /** The round's page should take the full reading width to hold a plate. */
  const occupies = (roundId: string) => byRound.value.get(roundId)?.hidden === false

  const state = { chatId, byRound, enabled, gallery, backdrop, viewing, promptOf, choosingFocus, illustrate, setHidden, busy, occupies }
  provide(KEY, state)
  return state
}

const KEY: InjectionKey<ReturnType<typeof provideChatIllustrations>> = Symbol('chat-illustrations')

export function useChatIllustrations() {
  const state = inject(KEY)
  if (!state) throw new Error('provideChatIllustrations was not called')
  return state
}
