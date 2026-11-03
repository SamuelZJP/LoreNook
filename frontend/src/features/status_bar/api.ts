import { request, type Schemas } from '@/api/client'
import type { ArchiveProgress } from '@/api/endpoints'

export type StatusBar = Schemas['StatusBar']
export type ChatStatusBar = Schemas['ChatStatusBar']
export type ChatStatusBarPatch = Schemas['ChatStatusBarPatch']

const json = (method: string, body?: unknown) => ({ method, body })

export const statusBarApi = {
  card: (characterId: string) => request<StatusBar>(`/api/characters/${characterId}/status-bar`),
  putCard: (characterId: string, code: string) =>
    request<StatusBar>(`/api/characters/${characterId}/status-bar`, json('PUT', { code })),
  chat: (chatId: string) => request<ChatStatusBar>(`/api/chats/${chatId}/status-bar`),
  patchChat: (chatId: string, body: ChatStatusBarPatch) =>
    request<ChatStatusBar>(`/api/chats/${chatId}/status-bar`, json('PATCH', body)),
  /** A round with the state it ended in; core endpoint. */
  round: (chatId: string, roundId: string) => request<ArchiveProgress>(`/api/chats/${chatId}/rounds/${roundId}`),
}
