import { computed, inject, provide, reactive, type InjectionKey, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api, type RoundRead } from '@/api/endpoints'
import { statusBarApi } from './api'

/** The status bar of one open chat, shared by the pieces placed inside the chat view. */
export function provideChatStatusBar(chatId: Ref<string>, rounds: Ref<RoundRead[]>, names: Ref<{ character: string; identity: string }>) {
  const query = useQuery({ queryKey: computed(() => ['status-bar', chatId.value]), queryFn: () => statusBarApi.chat(chatId.value) })
  const code = computed(() => query.data.value?.code ?? '')
  const active = computed(() => !!query.data.value?.enabled && !!code.value.trim())

  /** The newest round that has its own state; its bar is always shown. */
  const latestId = computed(() => rounds.value.filter((r) => r.archive_step !== 'state_update').at(-1)?.id ?? null)
  // Its state is the chat's latest state, which the state panel edits in place.
  const latestState = useQuery({
    queryKey: computed(() => ['state', chatId.value]),
    queryFn: () => api.state(chatId.value),
    enabled: computed(() => active.value && latestId.value !== null),
  })

  /** Earlier rounds whose bar the reader opened. */
  const opened = reactive(new Set<string>())
  const isOpen = (roundId: string) => roundId === latestId.value || opened.has(roundId)
  function toggle(roundId: string) {
    if (opened.has(roundId)) opened.delete(roundId)
    else opened.add(roundId)
  }

  const value = { chatId, code, active, latestId, latestState, names, isOpen, toggle, opened }
  provide(KEY, value)
  return value
}

const KEY: InjectionKey<ReturnType<typeof provideChatStatusBar>> = Symbol('chat-status-bar')

export function useChatStatusBar() {
  const value = inject(KEY)
  if (!value) throw new Error('useChatStatusBar needs provideChatStatusBar in an ancestor')
  return value
}
