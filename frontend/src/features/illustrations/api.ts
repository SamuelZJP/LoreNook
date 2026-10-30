import { request, type Schemas } from '@/api/client'

export type ImageWorkflow = Schemas['ImageWorkflowRead']
export type ImageWorkflowCreate = Schemas['ImageWorkflowCreate']
export type ImageWorkflowPatch = Schemas['ImageWorkflowPatch']
export type Illustration = Schemas['IllustrationRead']
export type IllustrationSettings = Schemas['IllustrationSettings']
export type IllustrationMode = IllustrationSettings['mode']
export type CastMember = Schemas['CastMemberRead']
export type CastMemberInput = Schemas['CastMemberInput']
export type Appearance = Schemas['AppearanceInput']
export type FocusOptions = Schemas['FocusOptions']

export type WorkflowScope = { chatId: string | null }

const json = (method: string, body?: unknown) => ({ method, body })
const workflowBase = (s: WorkflowScope) => (s.chatId ? `/api/chats/${s.chatId}/image-workflows` : '/api/image-workflows')

export const illustrationApi = {
  workflows: (s: WorkflowScope) => request<ImageWorkflow[]>(workflowBase(s)),
  createWorkflow: (s: WorkflowScope, body: ImageWorkflowCreate) => request<ImageWorkflow>(workflowBase(s), json('POST', body)),
  patchWorkflow: (s: WorkflowScope, id: string, body: ImageWorkflowPatch) =>
    request<ImageWorkflow>(`${workflowBase(s)}/${id}`, json('PATCH', body)),
  deleteWorkflow: (s: WorkflowScope, id: string) => request<void>(`${workflowBase(s)}/${id}`, json('DELETE')),
  importWorkflow: (chatId: string, sourceId: string) =>
    request<ImageWorkflow>(`/api/chats/${chatId}/image-workflows/import`, json('POST', { source_id: sourceId })),
  defaultTemplates: () => request<Schemas['DefaultTemplates']>('/api/image-workflows/default-templates'),

  settings: (chatId: string) => request<IllustrationSettings>(`/api/chats/${chatId}/illustration-settings`),
  putSettings: (chatId: string, body: IllustrationSettings) =>
    request<IllustrationSettings>(`/api/chats/${chatId}/illustration-settings`, json('PUT', body)),
  setup: (chatId: string, body: Schemas['IllustrationSetup']) =>
    request<IllustrationSettings>(`/api/chats/${chatId}/illustration-setup`, json('POST', body)),
  focusOptions: (chatId: string) => request<FocusOptions>(`/api/chats/${chatId}/focus-options`),

  // `owner` is `/api/characters/{id}` or `/api/chats/{id}`.
  cast: (owner: string) => request<CastMember[]>(`${owner}/cast`),
  putCast: (owner: string, members: CastMemberInput[]) => request<CastMember[]>(`${owner}/cast`, json('PUT', { members })),
  // `owner` is `/api/user-identities/{id}` or `/api/chats/{id}`.
  appearance: (owner: string) => request<Appearance>(`${owner}/appearance`),
  putAppearance: (owner: string, body: Appearance) => request<Appearance>(`${owner}/appearance`, json('PUT', body)),

  illustrations: (chatId: string) => request<Illustration[]>(`/api/chats/${chatId}/illustrations`),
  illustrate: (chatId: string, roundId: string, focus?: string[]) =>
    request<Illustration>(`/api/chats/${chatId}/rounds/${roundId}/illustrations`, json('POST', focus ? { focus } : undefined)),
  patchIllustration: (chatId: string, id: string, body: Schemas['IllustrationPatch']) =>
    request<Illustration>(`/api/chats/${chatId}/illustrations/${id}`, json('PATCH', body)),
  image: (chatId: string, id: string) => `/api/chats/${chatId}/illustrations/${id}/image`,
}
