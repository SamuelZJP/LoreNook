import { request } from './client'
import type { Schemas } from './client'

export type Character = Schemas['CharacterRead']
export type CharacterCreate = Schemas['CharacterCreate']
export type CharacterPatch = Schemas['CharacterPatch']
export type Scene = Schemas['SceneRead']
export type SceneInput = Schemas['SceneInput']
export type Identity = Schemas['IdentityRead']
export type IdentityCreate = Schemas['IdentityCreate']
export type IdentityPatch = Schemas['IdentityPatch']
export type Definition = Schemas['DefinitionRead']
export type DefinitionInput = Schemas['DefinitionInput']
export type DefinitionPatch = Schemas['DefinitionPatch']
export type Chat = Schemas['ChatRead']
export type ChatDetail = Schemas['ChatDetail']
export type ChatCreate = Schemas['ChatCreate']
export type ChatPatch = Schemas['ChatPatch']
export type Preset = Schemas['PresetRead']
export type ModelConfig = Schemas['ModelConfigRead']
export type ModelConfigCreate = Schemas['ModelConfigCreate']
export type ModelConfigPatch = Schemas['ModelConfigPatch']
export type StateRead = Schemas['StateRead']
export type RoundRead = Schemas['RoundRead']
export type ArchiveProgress = Schemas['ArchiveProgress']
export type Episode = Schemas['EpisodeRead']
export type WritingResult = Schemas['WritingResult']
export type ChatMemory = Schemas['ChatMemory']
export type BuiltRequest = Schemas['BuiltRequest']
export type WritingMaterials = Schemas['WritingMaterials']
export type AdminTableInfo = Schemas['AdminTableInfo']
export type AdminSnapshot = Schemas['AdminSnapshot']
export type AdminBatch = Schemas['AdminBatch']
export type AdminBatchResult = Schemas['AdminBatchResult']
export type ModelPurpose = 'writing' | 'state_update' | 'round_summary' | 'episode_summary'
export type PendingStep = Schemas['ArchiveRetry']['expected_step']

export const MODEL_PURPOSES: ModelPurpose[] = ['writing', 'state_update', 'round_summary', 'episode_summary']
export const API_TYPES = ['google_generate_content', 'deepseek_chat_completions'] as const

const json = (method: string, body?: unknown) => ({ method, body })

/** Base path for a scope: source library (`null`) or a chat's own copies. */
export type Scope = { chatId: string | null }

export const api = {
  // Source characters and identities
  characters: () => request<Character[]>('/api/characters'),
  character: (id: string) => request<Character>(`/api/characters/${id}`),
  createCharacter: (body: CharacterCreate) => request<Character>('/api/characters', json('POST', body)),
  patchCharacter: (id: string, body: CharacterPatch) => request<Character>(`/api/characters/${id}`, json('PATCH', body)),
  deleteCharacter: (id: string) => request<void>(`/api/characters/${id}`, json('DELETE')),
  previewInitialState: (body: Schemas['InitialStatePreview']) =>
    request<Record<string, unknown>>('/api/characters/initial-state-preview', json('POST', body)),
  identities: () => request<Identity[]>('/api/user-identities'),
  identity: (id: string) => request<Identity>(`/api/user-identities/${id}`),
  createIdentity: (body: IdentityCreate) => request<Identity>('/api/user-identities', json('POST', body)),
  patchIdentity: (id: string, body: IdentityPatch) => request<Identity>(`/api/user-identities/${id}`, json('PATCH', body)),
  deleteIdentity: (id: string) => request<void>(`/api/user-identities/${id}`, json('DELETE')),

  // Chat-owned character and identity copies
  chatCharacter: (chatId: string) => request<Character>(`/api/chats/${chatId}/character`),
  patchChatCharacter: (chatId: string, body: CharacterPatch) =>
    request<Character>(`/api/chats/${chatId}/character`, json('PATCH', body)),
  chatIdentity: (chatId: string) => request<Identity>(`/api/chats/${chatId}/user-identity`),
  patchChatIdentity: (chatId: string, body: IdentityPatch) =>
    request<Identity>(`/api/chats/${chatId}/user-identity`, json('PATCH', body)),

  // Definitions under any of the four owner bases
  definitions: (base: string) => request<Definition[]>(`${base}/definitions`),
  createDefinition: (base: string, body: DefinitionInput) => request<Definition>(`${base}/definitions`, json('POST', body)),
  patchDefinition: (base: string, id: string, body: DefinitionPatch) =>
    request<Definition>(`${base}/definitions/${id}`, json('PATCH', body)),
  deleteDefinition: (base: string, id: string) => request<void>(`${base}/definitions/${id}`, json('DELETE')),
  reorderDefinitions: (base: string, ids: string[]) =>
    request<Definition[]>(`${base}/definitions/reorder`, json('PUT', { definition_ids: ids })),
  resolveDefinitions: (chatId: string) =>
    request<Schemas['ChatResolvedDefinitions']>(`/api/chats/${chatId}/definitions/resolve`, json('POST')),

  // Chats
  chats: () => request<Chat[]>('/api/chats'),
  chat: (id: string) => request<ChatDetail>(`/api/chats/${id}`),
  createChat: (body: ChatCreate) => request<ChatDetail>('/api/chats', json('POST', body)),
  patchChat: (id: string, body: ChatPatch) => request<ChatDetail>(`/api/chats/${id}`, json('PATCH', body)),
  deleteChat: (id: string) => request<void>(`/api/chats/${id}`, json('DELETE')),
  memory: (chatId: string) => request<ChatMemory>(`/api/chats/${chatId}/memory`),
  memoryMaterials: (chatId: string) => request<Schemas['MemoryMaterials']>(`/api/chats/${chatId}/memory/materials`),

  // Presets (source or chat scope)
  presets: (s: Scope) => request<Preset[]>(presetBase(s)),
  createPreset: (s: Scope, body: Schemas['PresetCreate']) => request<Preset>(presetBase(s), json('POST', body)),
  patchPreset: (s: Scope, id: string, body: Schemas['PresetPatch']) =>
    request<Preset>(`${presetBase(s)}/${id}`, json('PATCH', body)),
  deletePreset: (s: Scope, id: string) => request<void>(`${presetBase(s)}/${id}`, json('DELETE')),
  buildPreset: (s: Scope, id: string, body: WritingMaterials) =>
    request<BuiltRequest>(`${presetBase(s)}/${id}/build`, json('POST', body)),
  parsePreset: (s: Scope, id: string, response: Record<string, unknown>) =>
    request<Schemas['ParsedOutput']>(`${presetBase(s)}/${id}/parse`, json('POST', { response })),
  writingPreview: (chatId: string, userInput: string, instruction: string) =>
    request<Schemas['WritingPreview']>(`/api/chats/${chatId}/writing-preview`, json('POST', { user_input: userInput, instruction })),

  // Model configurations (source or chat scope)
  models: (s: Scope) => request<ModelConfig[]>(modelBase(s)),
  createModel: (s: Scope, body: ModelConfigCreate) => request<ModelConfig>(modelBase(s), json('POST', body)),
  patchModel: (s: Scope, id: string, body: ModelConfigPatch) =>
    request<ModelConfig>(`${modelBase(s)}/${id}`, json('PATCH', body)),
  deleteModel: (s: Scope, id: string) => request<void>(`${modelBase(s)}/${id}`, json('DELETE')),
  invokeModel: (s: Scope, id: string, body: BuiltRequest) =>
    request<Schemas['ModelResponse']>(`${modelBase(s)}/${id}/invoke`, json('POST', body)),

  // Uploaded images
  uploadMedia: (file: Blob) => request<Schemas['MediaRead']>('/api/media', { method: 'POST', file }),

  // Writing and archiving
  write: (chatId: string, userInput: string, instruction: string) =>
    request<WritingResult>(`/api/chats/${chatId}/writing`, json('POST', { user_input: userInput, instruction })),
  confirm: (chatId: string, body: Schemas['ArchiveConfirm']) =>
    request<ArchiveProgress>(`/api/chats/${chatId}/archive`, json('POST', body)),
  archive: (chatId: string) => request<ArchiveProgress | null>(`/api/chats/${chatId}/archive`),
  retryArchive: (chatId: string, roundId: string, step: PendingStep) =>
    request<ArchiveProgress>(`/api/chats/${chatId}/rounds/${roundId}/archive/retry`, json('POST', { expected_step: step })),
  rounds: (chatId: string) => request<RoundRead[]>(`/api/chats/${chatId}/rounds`),

  // Latest-result editing
  state: (chatId: string) => request<StateRead>(`/api/chats/${chatId}/state`),
  putState: (chatId: string, content: Record<string, unknown>) =>
    request<StateRead>(`/api/chats/${chatId}/state`, json('PUT', { content })),
  putSummary: (chatId: string, roundId: string, summary: string) =>
    request<Schemas['RoundSummaryRead']>(`/api/chats/${chatId}/rounds/${roundId}/summary`, json('PUT', { summary })),
  episodes: (chatId: string) => request<Episode[]>(`/api/chats/${chatId}/episodes`),
  putEpisode: (chatId: string, id: string, body: Schemas['EpisodeReplace']) =>
    request<Episode>(`/api/chats/${chatId}/episodes/${id}`, json('PUT', body)),

  // Data management
  adminSchema: () => request<AdminTableInfo[]>('/api/admin/schema'),
  adminData: () => request<AdminSnapshot>('/api/admin/data'),
  adminBatch: (body: AdminBatch) => request<AdminBatchResult>('/api/admin/data', json('POST', body)),
}

function presetBase(s: Scope) {
  return s.chatId ? `/api/chats/${s.chatId}/writing-presets` : '/api/writing-presets'
}
function modelBase(s: Scope) {
  return s.chatId ? `/api/chats/${s.chatId}/model-configs` : '/api/model-configs'
}

export function definitionBase(kind: 'character' | 'identity', ownerId: string, chatId: string | null) {
  if (chatId) return kind === 'character' ? `/api/chats/${chatId}/character` : `/api/chats/${chatId}/user-identity`
  return kind === 'character' ? `/api/characters/${ownerId}` : `/api/user-identities/${ownerId}`
}
