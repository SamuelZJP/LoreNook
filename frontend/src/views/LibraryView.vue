<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useRoute, useRouter } from 'vue-router'
import { Plus, ArrowLeft, KeyRound } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import TopBar from '@/components/TopBar.vue'
import AvatarBadge from '@/components/AvatarBadge.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ProfileEditor from '@/components/editors/ProfileEditor.vue'
import PresetEditor from '@/components/editors/PresetEditor.vue'
import ModelEditor from '@/components/editors/ModelEditor.vue'
import WorkflowEditor from '@/features/illustrations/components/WorkflowEditor.vue'
import { illustrationApi } from '@/features/illustrations/api'

type Tab = 'characters' | 'identities' | 'presets' | 'models' | 'workflows'
const route = useRoute()
const router = useRouter()
const tab = computed<Tab>(() => (route.params.tab as Tab) || 'characters')
const selected = computed(() => (route.params.id as string) || null)
const editId = computed(() => (selected.value === 'new' ? null : selected.value))

const tabs: { id: Tab; label: string; noun: string }[] = [
  { id: 'characters', label: '角色', noun: '角色' },
  { id: 'identities', label: '用户身份', noun: '身份' },
  { id: 'presets', label: '写作预设', noun: '预设' },
  { id: 'models', label: '模型配置', noun: '模型' },
  { id: 'workflows', label: '图像工作流', noun: '工作流' },
]

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
const workflows = useQuery({ queryKey: ['workflows', null], queryFn: () => illustrationApi.workflows({ chatId: null }) })

const current = computed(() => ({ characters, identities, presets, models, workflows })[tab.value])
const items = computed(() => {
  switch (tab.value) {
    case 'characters': return (characters.data.value ?? []).map((c) => ({ id: c.id, name: c.name, avatar: c.avatar, sub: c.description }))
    case 'identities': return (identities.data.value ?? []).map((c) => ({ id: c.id, name: c.name, avatar: c.avatar, sub: c.description }))
    case 'presets': return (presets.data.value ?? []).map((p) => ({ id: p.id, name: p.name, avatar: undefined, sub: `${p.source.length} 字符` }))
    case 'workflows': return (workflows.data.value ?? []).map((w) => ({ id: w.id, name: w.name, avatar: undefined, sub: `${w.image_inputs.length ? '图生图' : '文生图'} · ${w.width}×${w.height}` }))
    default: return (models.data.value ?? []).map((m) => ({ id: m.id, name: m.name, avatar: undefined, sub: `${m.api_type} · ${m.model}`, key: m.has_api_key }))
  }
})

function go(id: string | null) {
  router.push(id ? `/library/${tab.value}/${id}` : `/library/${tab.value}`)
}
</script>

<template>
  <div class="library">
    <TopBar><h1 class="grow">资源库</h1></TopBar>
    <nav class="tabs lib-tabs">
      <RouterLink v-for="t in tabs" :key="t.id" v-slot="{ navigate }" :to="`/library/${t.id}`" custom>
        <button type="button" :class="{ active: tab === t.id }" @click="navigate">{{ t.label }}</button>
      </RouterLink>
    </nav>
    <div class="split" :class="{ detail: !!selected }">
      <div class="master">
        <div class="row master-head">
          <span class="faint grow">{{ items.length }} 项</span>
          <button class="btn small primary" type="button" @click="go('new')"><Plus /> 新建{{ tabs.find((t) => t.id === tab)!.noun }}</button>
        </div>
        <ErrorBox v-if="current.error.value" :error="current.error.value" />
        <div v-else-if="!items.length && !current.isLoading.value" class="empty">还没有内容</div>
        <div class="stack tight">
          <button
            v-for="it in items" :key="it.id" type="button" class="list-item" :class="{ active: selected === it.id }"
            @click="go(it.id)"
          >
            <AvatarBadge v-if="tab === 'characters' || tab === 'identities'" :name="it.name" :src="it.avatar" :size="34" />
            <div class="grow">
              <div class="ellipsis name">{{ it.name }}</div>
              <div class="faint ellipsis sub">{{ it.sub || '—' }}</div>
            </div>
            <KeyRound v-if="'key' in it && it.key" class="key" />
          </button>
        </div>
      </div>
      <div class="detail-pane">
        <div v-if="!selected" class="empty">选择左侧条目进行编辑，或新建一个。</div>
        <div v-else class="detail-inner">
          <button class="btn ghost small back" type="button" @click="go(null)"><ArrowLeft /> 返回列表</button>
          <div class="card card-pad">
            <ProfileEditor
              v-if="tab === 'characters' || tab === 'identities'" :key="`${tab}-${selected}`"
              :kind="tab === 'characters' ? 'character' : 'identity'" :id="editId" :chat-id="null"
              @saved="(id) => selected === 'new' && go(id)" @deleted="go(null)"
            />
            <PresetEditor v-else-if="tab === 'presets'" :key="`p-${selected}`" :id="editId" :chat-id="null" @saved="(id) => selected === 'new' && go(id)" @deleted="go(null)" />
            <WorkflowEditor v-else-if="tab === 'workflows'" :key="`w-${selected}`" :id="editId" :chat-id="null" @saved="(id) => selected === 'new' && go(id)" @deleted="go(null)" />
            <ModelEditor v-else :key="`m-${selected}`" :id="editId" :chat-id="null" @saved="(id) => selected === 'new' && go(id)" @deleted="go(null)" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.library { display: flex; flex-direction: column; height: 100%; }
.lib-tabs { padding: 0 12px; background: var(--bg-elev); flex-shrink: 0; }
.split { flex: 1; min-height: 0; display: flex; }
.master { width: 320px; flex-shrink: 0; border-right: 1px solid var(--border); overflow-y: auto; padding: 12px 10px; }
.master-head { margin-bottom: 8px; padding: 0 4px; }
.list-item { width: 100%; border: 0; background: none; text-align: left; font: inherit; color: inherit; }
.name { font-weight: 500; }
.sub { font-size: 12px; }
.key { width: 14px; height: 14px; color: var(--ok); }
.detail-pane { flex: 1; min-width: 0; overflow-y: auto; }
.detail-inner { max-width: 900px; margin: 0 auto; padding: 16px 16px 48px; }
.back { display: none; margin-bottom: 8px; }
@media (max-width: 899px) {
  .master { width: 100%; border-right: 0; }
  .detail-pane { display: none; }
  .split.detail .master { display: none; }
  .split.detail .detail-pane { display: block; }
  .back { display: inline-flex; }
  .detail-inner { padding: 12px 10px 48px; }
}
</style>
