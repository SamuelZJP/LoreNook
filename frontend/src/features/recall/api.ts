import { request, type Schemas } from '@/api/client'

export type RecallSettings = Schemas['RecallSettings']
export type RecallResult = Schemas['RecallResult']

const json = (method: string, body?: unknown) => ({ method, body })

export const recallApi = {
  recall: (chatId: string, userInput: string, instruction: string) =>
    request<RecallResult>(`/api/chats/${chatId}/recall`, json('POST', { user_input: userInput, instruction })),
  settings: (chatId: string) => request<RecallSettings>(`/api/chats/${chatId}/recall-settings`),
  putSettings: (chatId: string, body: RecallSettings) =>
    request<RecallSettings>(`/api/chats/${chatId}/recall-settings`, json('PUT', body)),
  setup: (chatId: string, body: RecallSettings) =>
    request<RecallSettings>(`/api/chats/${chatId}/recall-setup`, json('POST', body)),
}
