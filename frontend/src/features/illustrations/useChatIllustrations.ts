import { computed, inject, nextTick, onScopeDispose, provide, reactive, ref, watch, type InjectionKey, type Ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { RoundRead } from '@/api/endpoints'
import { toast } from '@/composables/toast'
import { illustrationApi, type Illustration, type IllustrationProgress } from './api'
import { isActive, illustrationPrefs } from './lib'
import { pickReadingRound } from './reading'

/** Where the chat view is laid out: `docked` while the side panel sits beside the conversation. */
export interface IllustrationLayout { docked: Ref<boolean>; scroller: Ref<HTMLElement | undefined> }

/**
 * The illustration state of one open chat, shared by the pieces placed inside the chat view.
 * While the panel is docked, plates leave the reading column for the panel, which shows the
 * illustration of the round being read.
 */
export function provideChatIllustrations(chatId: Ref<string>, rounds: Ref<RoundRead[]>, layout: IllustrationLayout) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: computed(() => ['illustrations', chatId.value]),
    queryFn: () => illustrationApi.illustrations(chatId.value),
    // The progress stream drives updates; this only covers a stream that can't get through.
    refetchInterval: (q) => ((q.state.data ?? []).some(isActive) ? 15000 : false),
  })
  const settings = useQuery({
    queryKey: computed(() => ['illustration-settings', chatId.value]),
    queryFn: () => illustrationApi.settings(chatId.value),
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['illustrations', chatId.value] })

  /** Live state of running jobs by illustration id, while the stream is open. */
  const progress = ref<Record<string, IllustrationProgress>>({})
  let stream: EventSource | null = null
  function closeStream() {
    stream?.close()
    stream = null
    progress.value = {}
  }
  function openStream() {
    stream = new EventSource(illustrationApi.progressUrl(chatId.value))
    stream.onmessage = (event) => {
      const next: Record<string, IllustrationProgress> = JSON.parse(event.data)
      const before = progress.value
      progress.value = next
      // A job started, advanced or ended: the list holds its stored fields.
      if ([...Object.keys(before), ...Object.keys(next)].some((id) => before[id]?.status !== next[id]?.status)) refresh()
    }
  }
  const running = computed(() => (query.data.value ?? []).some(isActive))
  watch([running, chatId], ([on]) => {
    closeStream()
    if (on) openStream()
  }, { immediate: true })
  onScopeDispose(closeStream)

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

  // Each illustrated round shown in the timeline registers its marker; the reading round follows the scroll.
  const docked = layout.docked
  const markers = new Map<string, HTMLElement>()
  const reading = ref<string | null>(null)
  function mark(roundId: string, el: HTMLElement | null) {
    if (el) markers.set(roundId, el)
    else markers.delete(roundId)
  }
  function locate() {
    const view = layout.scroller.value
    if (!docked.value || !view) return
    const top = view.getBoundingClientRect().top
    const order = new Map(rounds.value.map((r, i) => [r.id, i]))
    const marks = [...markers.entries()]
      .map(([roundId, el]) => ({ roundId, top: el.getBoundingClientRect().top - top }))
      .sort((a, b) => (order.get(a.roundId) ?? 0) - (order.get(b.roundId) ?? 0))
    const atEnd = view.scrollHeight - view.scrollTop - view.clientHeight < 8
    reading.value = pickReadingRound(marks, view.clientHeight / 2, atEnd)
  }
  let frame = 0
  const onScroll = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(locate) }
  watch(layout.scroller, (el, old) => {
    old?.removeEventListener('scroll', onScroll)
    el?.addEventListener('scroll', onScroll, { passive: true })
  }, { immediate: true })
  watch([docked, byRound, rounds], () => nextTick(locate))
  onScopeDispose(() => { layout.scroller.value?.removeEventListener('scroll', onScroll); cancelAnimationFrame(frame) })
  /** Show a round's illustration in the panel, e.g. from its marker. */
  const show = (roundId: string) => { reading.value = roundId }
  /** The illustration the docked panel shows: the reading round's, else the newest. */
  const current = computed(() => {
    const own = reading.value ? byRound.value.get(reading.value) : undefined
    if (own) return own
    const latest = rounds.value.filter((r) => byRound.value.has(r.id)).at(-1)
    return latest ? byRound.value.get(latest.id)! : null
  })

  const state = {
    chatId, byRound, progress, enabled, gallery, backdrop, viewing, promptOf, choosingFocus, illustrate, setHidden, busy, occupies,
    docked, reading, current, mark, show,
  }
  provide(KEY, state)
  return state
}

const KEY: InjectionKey<ReturnType<typeof provideChatIllustrations>> = Symbol('chat-illustrations')

export function useChatIllustrations() {
  const state = inject(KEY)
  if (!state) throw new Error('provideChatIllustrations was not called')
  return state
}
