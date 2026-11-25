import { useQueryClient } from '@tanstack/vue-query'
import { api, MODEL_PURPOSES, type ChatDetail, type ChatPatch, type ModelPurpose } from '@/api/endpoints'

/** Patch the chat and refresh what depends on it. */
export function useChatPatch(chatId: () => string) {
  const qc = useQueryClient()
  return async (patch: ChatPatch) => {
    const updated = await api.patchChat(chatId(), patch)
    qc.setQueryData(['chat', chatId()], updated)
    qc.invalidateQueries({ queryKey: ['chats'] })
    if ('recent_rounds' in patch || 'min_summaries' in patch) qc.invalidateQueries({ queryKey: ['memory', chatId()] })
  }
}

/** The whole binding map with one purpose changed; the API replaces the map. */
export function bindingsWith(chat: ChatDetail, purpose: ModelPurpose, modelId: string): Partial<Record<ModelPurpose, string>> {
  const out: Partial<Record<ModelPurpose, string>> = {}
  for (const p of MODEL_PURPOSES) {
    const id = p === purpose ? modelId : chat.model_bindings[p]
    if (id) out[p] = id
  }
  return out
}

/** Purposes of the steps that run after each confirmed round. */
export const ARCHIVE_PURPOSES = ['state_update', 'round_summary', 'episode_summary'] as const satisfies readonly ModelPurpose[]
