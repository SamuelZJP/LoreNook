<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, type Component } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { Archive, Brain, ChevronRight, Feather, Trash2 } from 'lucide-vue-next'
import { api, type ChatDetail } from '@/api/endpoints'
import { provideSaveTracker } from '@/composables/autosave'
import { toast } from '@/composables/toast'
import { CHAT_SETTINGS } from '@/features/chatSettings'
import type { CorePage } from './settings/contract'
import { ARCHIVE_PURPOSES, useChatPatch } from './settings/chatPatch'
import WritingPage from './settings/WritingPage.vue'
import MemoryPage from './settings/MemoryPage.vue'
import ArchivePage from './settings/ArchivePage.vue'
import SaveStatusLine from './settings/SaveStatusLine.vue'

/**
 * A chat's settings in two levels: a short list of rows with what each is set to,
 * and a page per row. Every change saves itself.
 */
const props = defineProps<{ chat: ChatDetail }>()
const qc = useQueryClient()
const router = useRouter()
const tracker = provideSaveTracker()
const patch = useChatPatch(() => props.chat.id)

// ---- Rows: the core ones, then whatever features add, by order ----
interface Row {
  id: string
  label: string
  icon: Component
  order: number
  summary?: string
  Summary?: Component
  Page?: Component
  core?: CorePage
}
const modelName = (id?: string | null) => props.chat.model_configs.find((m) => m.id === id)?.name
const writingSummary = computed(() => {
  const preset = props.chat.writing_presets.find((p) => p.id === props.chat.writing_preset_id)?.name ?? '未选写作风格'
  return `${preset} · ${modelName(props.chat.model_bindings.writing) ?? '未选模型'}`
})
const archiveSummary = computed(() => {
  const names = ARCHIVE_PURPOSES.map((p) => modelName(props.chat.model_bindings[p]))
  if (names.every((n) => !n)) return '未设置'
  if (names.every((n) => n && n === names[0])) return `都用 ${names[0]}`
  return `${names.filter(Boolean).length} / ${names.length} 项已设置`
})
const rows = computed<Row[]>(() => {
  const core: Row[] = [
    { id: 'writing', label: '写作', icon: Feather, order: 10, summary: writingSummary.value, Page: WritingPage, core: 'writing' },
    { id: 'memory', label: '记忆', icon: Brain, order: 20, summary: `原文 ${props.chat.recent_rounds} 回合`, Page: MemoryPage, core: 'memory' },
    { id: 'archive', label: '后台整理', icon: Archive, order: 30, summary: archiveSummary.value, Page: ArchivePage, core: 'archive' },
  ]
  return [...core, ...CHAT_SETTINGS.flatMap((c) => c.rows ?? [])].sort((a, b) => a.order - b.order)
})
const blocks = (page?: CorePage) => CHAT_SETTINGS.flatMap((c) => c.blocks ?? []).filter((b) => b.page === page).sort((a, b) => a.order - b.order)

// ---- Navigation ----
const openId = ref<string | null>(null)
const open = computed(() => rows.value.find((r) => r.id === openId.value) ?? null)
/** Save what is pending, then go back; stay if a save failed so the error shows. */
async function finish() {
  if (await tracker.flush()) openId.value = null
}
watch(() => props.chat.id, () => (openId.value = null))
onBeforeUnmount(() => tracker.flush())

// ---- Title, edited right on the list ----
const title = ref(props.chat.title)
watch(() => props.chat.title, (v) => (title.value = v))
function saveTitle(delay = 600) {
  const t = title.value.trim()
  if (t && t !== props.chat.title) tracker.schedule('title', () => patch({ title: t }), delay)
}

async function removeChat() {
  if (!confirm(`删除聊天“${props.chat.title}”及其全部回合、状态和副本？此操作不可撤销。`)) return
  try {
    await api.deleteChat(props.chat.id)
    qc.invalidateQueries({ queryKey: ['chats'] })
    toast('聊天已删除')
    router.push('/')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  }
}
</script>

<template>
  <!-- One row's page -->
  <div v-if="open" class="settings-page">
    <div class="page-head">
      <button class="crumb" type="button" @click="finish"><component :is="open.icon" /> {{ open.label }}</button>
      <span class="grow" />
      <button class="btn small primary" type="button" :disabled="tracker.status.value === 'saving'" @click="finish">
        完成
      </button>
    </div>
    <component :is="open.Page" :chat="chat" />
    <template v-for="(b, i) in blocks(open.core)" :key="i">
      <hr class="divider" />
      <component :is="b.Block" :chat="chat" />
    </template>
    <SaveStatusLine :tracker="tracker" class="status" />
  </div>

  <!-- The list -->
  <div v-else class="settings-list">
    <div class="field">
      <label for="chat-title">标题</label>
      <input id="chat-title" v-model="title" class="input title-input" @input="saveTitle()" @blur="saveTitle(0)" @keydown.enter="saveTitle(0)" />
    </div>
    <div class="rows card">
      <component
        :is="r.Page ? 'button' : 'div'" v-for="r in rows" :key="r.id" class="row-item" :class="{ link: !!r.Page }"
        :type="r.Page ? 'button' : undefined" @click="r.Page && (openId = r.id)"
      >
        <component :is="r.icon" class="row-icon" />
        <span class="row-label">{{ r.label }}</span>
        <span class="row-summary">
          <template v-if="r.summary">{{ r.summary }}</template>
          <template v-for="(b, i) in blocks(r.core).filter((b) => b.Summary)" :key="i"> · <component :is="b.Summary" :chat="chat" /></template>
          <component :is="r.Summary" v-if="r.Summary" :chat="chat" />
        </span>
        <ChevronRight v-if="r.Page" class="chev" />
      </component>
    </div>
    <SaveStatusLine :tracker="tracker" />
    <div class="danger-zone">
      <button class="btn ghost small danger" type="button" @click="removeChat"><Trash2 /> 删除这个聊天</button>
    </div>
  </div>
</template>

<style scoped>
.settings-list, .settings-page { display: flex; flex-direction: column; gap: var(--space-3); }
.title-input { font-family: var(--font-reading); font-size: var(--text-lg); }
.rows { display: flex; flex-direction: column; overflow: hidden; }
.row-item {
  display: flex; align-items: center; gap: var(--space-3); min-height: 56px; padding: var(--space-2) var(--space-3);
  border: 0; border-bottom: 1px solid var(--border); background: none; color: inherit; font: inherit; text-align: left; width: 100%;
}
.row-item:last-child { border-bottom: 0; }
.row-item.link { cursor: pointer; }
.row-item.link:hover { background: var(--bg-hover); }
.row-icon { width: 18px; height: 18px; color: var(--accent); flex-shrink: 0; }
.row-label { font-weight: 600; flex-shrink: 0; }
.row-summary {
  flex: 1; min-width: 0; text-align: right; font-size: var(--text-xs); color: var(--text-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.chev { width: 16px; height: 16px; color: var(--text-faint); flex-shrink: 0; }
.danger-zone { margin-top: var(--space-6); padding-top: var(--space-3); border-top: 1px solid var(--border); }

.page-head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); }
.crumb {
  display: inline-flex; align-items: center; gap: var(--space-1-5); border: 0; background: none; padding: 0; cursor: pointer;
  font: inherit; font-size: var(--text-lg); font-weight: 600; color: var(--text);
}
.crumb svg { width: 18px; height: 18px; color: var(--accent); }
.divider { border: 0; border-top: 1px solid var(--border); margin: var(--space-2) 0; width: 100%; }
.status { margin-top: var(--space-2); }
</style>
