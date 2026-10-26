import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api, type ArchiveProgress, type WritingResult } from '@/api/endpoints'
import { ApiError } from '@/api/client'
import { pendingStep } from '@/lib/archive'

export type Phase =
  | 'idle'          // ready for a new input
  | 'generating'    // waiting for a candidate
  | 'candidate'     // unsaved candidate awaiting confirmation
  | 'archiving'     // confirmation or retry request in flight
  | 'checking'      // re-reading progress after an unknown outcome
  | 'incomplete'    // latest saved round has unfinished archive steps

export interface FlowError {
  action: 'generate' | 'confirm' | 'retry' | 'check'
  error: unknown
  note?: string
}

/**
 * Round lifecycle for one chat. Server progress is the source of truth for anything saved;
 * only the unsaved candidate lives in memory (and is lost on reload by design).
 */
export function useRoundFlow(chatId: Ref<string>) {
  const qc = useQueryClient()
  const input = ref('')
  const candidate = ref<WritingResult | null>(null)
  const busy = ref<null | 'generating' | 'archiving' | 'checking'>(null)
  const error = ref<FlowError | null>(null)
  const startedAt = ref(0)
  /** The model's own output for the current candidate, kept so user edits can be reverted. */
  const original = ref<string | null>(null)
  /** Text in the candidate editor; null while not editing. */
  const draft = ref<string | null>(null)

  const archive = useQuery({
    queryKey: computed(() => ['archive', chatId.value]),
    queryFn: () => api.archive(chatId.value),
    // While an archive request runs, poll progress so the UI can show the current step.
    refetchInterval: computed(() => (busy.value === 'archiving' ? 2500 : false)),
  })

  watch(chatId, () => {
    input.value = ''
    candidate.value = null
    error.value = null
    busy.value = null
  })

  const latestRound = computed(() => archive.data.value?.round ?? null)
  const unfinished = computed(() => pendingStep(latestRound.value))

  // Edits belong to one candidate: drop them once it is saved, discarded or replaced.
  watch(candidate, (c) => {
    if (!c) original.value = null
    draft.value = null
  })

  const editing = computed(() => draft.value !== null)
  const edited = computed(() => !!candidate.value && original.value !== null && candidate.value.ai_output !== original.value)
  /** Regenerating or discarding now would throw away the user's edits. */
  const hasEdits = computed(() => edited.value || (editing.value && draft.value !== candidate.value?.ai_output))

  function startEdit() {
    if (candidate.value) draft.value = candidate.value.ai_output
  }
  function applyEdit() {
    if (candidate.value && draft.value !== null) candidate.value = { ...candidate.value, ai_output: draft.value }
  }
  function cancelEdit() {
    draft.value = null
  }
  function revertEdit() {
    if (candidate.value && original.value !== null) candidate.value = { ...candidate.value, ai_output: original.value }
  }

  const phase = computed<Phase>(() => {
    if (busy.value === 'generating') return 'generating'
    if (busy.value === 'archiving') return 'archiving'
    if (busy.value === 'checking') return 'checking'
    if (unfinished.value) return 'incomplete'
    if (candidate.value) return 'candidate'
    return 'idle'
  })

  /** Input differs from the candidate's paired input: confirmation would mismatch them. */
  const inputChanged = computed(() => !!candidate.value && candidate.value.user_input !== input.value)

  function refreshAll() {
    const id = chatId.value
    for (const key of ['archive', 'rounds', 'chat', 'episodes', 'state', 'memory']) {
      qc.invalidateQueries({ queryKey: [key, id] })
    }
  }

  async function generate() {
    if (busy.value || unfinished.value) return
    busy.value = 'generating'
    startedAt.value = Date.now()
    error.value = null
    try {
      const result = await api.write(chatId.value, input.value)
      candidate.value = result
      original.value = result.ai_output
    } catch (e) {
      // A failed generation keeps the previous candidate (if any) and the typed input.
      error.value = { action: 'generate', error: e }
      if (e instanceof ApiError && e.status === 409) refreshAll()
    } finally {
      busy.value = null
    }
  }

  function discardCandidate() {
    candidate.value = null
    error.value = null
  }

  function applyProgress(progress: ArchiveProgress | null) {
    qc.setQueryData(['archive', chatId.value], progress)
    refreshAll()
  }

  async function confirm() {
    const c = candidate.value
    if (!c || busy.value || inputChanged.value || editing.value) return
    busy.value = 'archiving'
    startedAt.value = Date.now()
    error.value = null
    try {
      const progress = await api.confirm(chatId.value, {
        user_input: c.user_input,
        ai_output: c.ai_output,
        based_on_round_id: c.based_on_round_id,
      })
      candidate.value = null
      input.value = ''
      applyProgress(progress)
    } catch (e) {
      busy.value = null
      if (e instanceof ApiError && e.archive) {
        // Dialogue was saved; a later step failed. Recovery continues from the saved round.
        candidate.value = null
        input.value = ''
        error.value = { action: 'confirm', error: e }
        applyProgress(e.archive)
      } else if (e instanceof ApiError && e.transport) {
        await reconcileAfterLostResponse(c, e)
      } else {
        // Rejected before saving (stale candidate, invalid body): keep the candidate.
        error.value = { action: 'confirm', error: e }
        if (e instanceof ApiError && e.status === 409) refreshAll()
      }
    } finally {
      if (busy.value === 'archiving') busy.value = null
    }
  }

  /** The confirmation response was lost: read progress instead of resending. */
  async function reconcileAfterLostResponse(c: WritingResult, cause: unknown) {
    busy.value = 'checking'
    try {
      const progress = await api.archive(chatId.value)
      const saved = progress && progress.round.id !== c.based_on_round_id
        && progress.round.ai_output === c.ai_output && progress.round.user_input === c.user_input
      if (saved) {
        candidate.value = null
        input.value = ''
        error.value = progress.round.archive_step === 'complete' ? null : {
          action: 'confirm', error: cause, note: '确认请求的响应丢失，但回合已保存。请按需要继续归档。',
        }
      } else {
        error.value = {
          action: 'confirm', error: cause,
          note: '确认请求的响应丢失，且未检测到已保存的回合。服务器可能仍在处理；稍后可刷新进度后再决定是否重新确认。',
        }
      }
      applyProgress(progress)
    } catch (e) {
      error.value = { action: 'check', error: e, note: '无法读取归档进度，请检查后端是否在运行后刷新。' }
    } finally {
      busy.value = null
    }
  }

  async function retry() {
    const round = latestRound.value
    const step = unfinished.value
    if (!round || !step || busy.value) return
    busy.value = 'archiving'
    startedAt.value = Date.now()
    error.value = null
    try {
      applyProgress(await api.retryArchive(chatId.value, round.id, step))
    } catch (e) {
      error.value = { action: 'retry', error: e }
      if (e instanceof ApiError && e.archive) applyProgress(e.archive)
      else await checkProgress()
    } finally {
      if (busy.value === 'archiving') busy.value = null
    }
  }

  async function checkProgress() {
    const prev = busy.value
    if (!prev) busy.value = 'checking'
    try {
      applyProgress(await api.archive(chatId.value))
    } catch (e) {
      error.value = { action: 'check', error: e }
    } finally {
      if (!prev) busy.value = null
    }
  }

  // Elapsed seconds for long waits.
  const now = ref(Date.now())
  const timer = setInterval(() => (now.value = Date.now()), 1000)
  onBeforeUnmount(() => clearInterval(timer))
  const elapsed = computed(() => (busy.value ? Math.max(0, Math.floor((now.value - startedAt.value) / 1000)) : 0))

  return {
    input, candidate, phase, error, elapsed, inputChanged, archive, latestRound, unfinished,
    draft, editing, edited, hasEdits,
    generate, confirm, retry, discardCandidate, checkProgress, refreshAll,
    startEdit, applyEdit, cancelEdit, revertEdit,
  }
}

export type RoundFlow = ReturnType<typeof useRoundFlow>
