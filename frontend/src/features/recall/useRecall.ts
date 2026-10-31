import { computed, ref, watch, type Ref } from 'vue'
import type { WriteRequest, WriteStep } from '@/composables/roundFlow'
import { recallApi, type RecallResult } from './api'

const keyOf = (request: WriteRequest) => JSON.stringify([request.input, request.instruction])

/**
 * Recall for one chat, as the step the round flow runs before writing.
 * A result is reused until the input or instruction changes, or the flow resets it.
 */
export function useRecall(chatId: Ref<string>) {
  const stored = ref<{ key: string; result: RecallResult } | null>(null)
  const reset = () => { stored.value = null }
  watch(chatId, reset)

  const step: WriteStep = {
    label: '正在唤醒记忆…',
    async prepare(request) {
      const key = keyOf(request)
      if (stored.value?.key !== key) {
        reset()
        stored.value = { key, result: await recallApi.recall(chatId.value, request.input, request.instruction) }
      }
      return stored.value.result.layout
    },
    current: (request) => (stored.value?.key === keyOf(request) ? stored.value.result.layout : null),
    reset,
  }

  /** What the memory panel should show while a recall result is in effect. */
  const timeline = computed(() => stored.value?.result.timeline ?? null)
  return { step, timeline }
}
