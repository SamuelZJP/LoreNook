<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Eye } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import TopBar from '@/components/TopBar.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ProfileEditor from '@/components/editors/ProfileEditor.vue'
import PresetEditor from '@/components/editors/PresetEditor.vue'
import ModelEditor from '@/components/editors/ModelEditor.vue'
import ChatTemplateEditor from '@/components/editors/ChatTemplateEditor.vue'
import WorkflowEditor from '@/features/illustrations/components/WorkflowEditor.vue'
import { illustrationApi } from '@/features/illustrations/api'
import LibraryHub from '@/components/library/LibraryHub.vue'
import LibraryCards, { type CardItem } from '@/components/library/LibraryCards.vue'
import { kindInfo, type LibraryKind } from '@/components/library/kinds'

/** Three levels: the hub, one kind's cards, one record's editor. */
const route = useRoute()
const router = useRouter()
const kind = computed(() => (route.params.tab as LibraryKind) || null)
const selected = computed(() => (route.params.id as string) || null)
const editId = computed(() => (selected.value === 'new' ? null : selected.value))
const info = computed(() => (kind.value ? kindInfo(kind.value) : null))

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
const workflows = useQuery({ queryKey: ['workflows', null], queryFn: () => illustrationApi.workflows({ chatId: null }) })
const templates = useQuery({ queryKey: ['chat-templates'], queryFn: api.chatTemplates })
const queries = { characters, identities, presets, models, workflows, templates }

const counts = computed(() => Object.fromEntries(
  Object.entries(queries).map(([k, q]) => [k, q.data.value?.length]),
) as Partial<Record<LibraryKind, number>>)

const items = computed<CardItem[]>(() => {
  switch (kind.value) {
    case 'characters': return (characters.data.value ?? []).map((c) => ({ id: c.id, name: c.name, avatar: c.avatar, portrait: c.portrait, sub: c.description }))
    case 'identities': return (identities.data.value ?? []).map((c) => ({ id: c.id, name: c.name, avatar: c.avatar, portrait: c.portrait, sub: c.description }))
    case 'presets': return (presets.data.value ?? []).map((p) => ({ id: p.id, name: p.name }))
    case 'templates': return (templates.data.value ?? []).map((t) => ({ id: t.id, name: t.name, badge: t.is_default ? '默认' : undefined }))
    case 'workflows': return (workflows.data.value ?? []).map((w) => ({ id: w.id, name: w.name, sub: `${w.width}×${w.height}` }))
    case 'models': return (models.data.value ?? []).map((m) => ({ id: m.id, name: m.name, sub: m.model, hasKey: m.has_api_key }))
    default: return []
  }
})
const current = computed(() => (kind.value ? queries[kind.value] : null))
const editorTitle = computed(() => {
  if (!info.value) return ''
  if (!editId.value) return `新建${info.value.noun}`
  return items.value.find((i) => i.id === editId.value)?.name ?? info.value.noun
})

function go(id: string | null) {
  router.replace(id ? `/library/${kind.value}/${id}` : `/library/${kind.value}`)
}
const onSaved = (id: string) => { if (selected.value === 'new') go(id) }
const onDeleted = () => go(null)
</script>

<template>
  <div class="library">
    <!-- Hub -->
    <template v-if="!kind">
      <TopBar class="narrow-only"><strong class="grow">资源库</strong></TopBar>
      <div class="page">
        <div class="inner">
          <h1 class="display">资源库</h1>
          <LibraryHub :counts="counts" />
        </div>
      </div>
    </template>

    <!-- One kind -->
    <template v-else-if="!selected">
      <TopBar><RouterLink to="/library" class="btn ghost small"><ArrowLeft /> 资源库</RouterLink></TopBar>
      <div class="page">
        <div class="inner">
          <h1 class="display">{{ info!.label }}</h1>
          <ErrorBox v-if="current?.error.value" :error="current.error.value" />
          <LibraryCards v-else :kind="kind" :items="items" />
        </div>
      </div>
    </template>

    <!-- One record -->
    <template v-else>
      <TopBar>
        <RouterLink :to="`/library/${kind}`" class="btn ghost small"><ArrowLeft /> {{ info!.label }}</RouterLink>
        <span class="grow" />
        <RouterLink v-if="kind === 'characters' && editId" :to="`/characters/${editId}`" class="btn ghost small"><Eye /> 角色页</RouterLink>
      </TopBar>
      <div class="page">
        <div class="inner editor">
          <h1 class="title">{{ editorTitle }}</h1>
          <ProfileEditor
            v-if="kind === 'characters' || kind === 'identities'" :key="`${kind}-${selected}`"
            :kind="kind === 'characters' ? 'character' : 'identity'" :id="editId" :chat-id="null"
            @saved="onSaved" @deleted="onDeleted"
          />
          <PresetEditor v-else-if="kind === 'presets'" :key="`p-${selected}`" :id="editId" :chat-id="null" @saved="onSaved" @deleted="onDeleted" />
          <ChatTemplateEditor v-else-if="kind === 'templates'" :key="`t-${selected}`" :id="editId" @saved="onSaved" @deleted="onDeleted" />
          <WorkflowEditor v-else-if="kind === 'workflows'" :key="`w-${selected}`" :id="editId" :chat-id="null" @saved="onSaved" @deleted="onDeleted" />
          <ModelEditor v-else :key="`m-${selected}`" :id="editId" :chat-id="null" @saved="onSaved" @deleted="onDeleted" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.library { display: flex; flex-direction: column; height: 100%; }
.library .page { flex: 1; }
.inner { max-width: 1200px; margin: 0 auto; padding: var(--space-8) var(--space-6) var(--space-12); display: flex; flex-direction: column; gap: var(--space-6); }
.inner.editor { max-width: 920px; gap: var(--space-4); }
.display { font-family: var(--font-reading); font-size: var(--text-display); font-weight: 600; letter-spacing: 0.06em; }
.title { font-family: var(--font-reading); font-size: var(--text-3xl); font-weight: 600; }
.narrow-only { display: none; }
@media (max-width: 899px) {
  .narrow-only { display: flex; }
  .inner { padding: var(--space-5) var(--space-4) var(--space-12); gap: var(--space-4); }
  .display { font-size: var(--text-3xl); }
  .title { font-size: var(--text-2xl); }
}
</style>
