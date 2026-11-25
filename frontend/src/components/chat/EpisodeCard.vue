<script setup lang="ts">
import { ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { BookOpen, Pencil } from 'lucide-vue-next'
import { api, type Episode } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'
import { toast } from '@/composables/toast'

const props = defineProps<{ chatId: string; episode: Episode; startNo?: number; endNo?: number; editable: boolean }>()
const qc = useQueryClient()
const open = ref(false)
const editing = ref(false)
const draft = ref({ title: '', summary: '' })
const saving = ref(false)
const error = ref<unknown>(null)

function start() {
  draft.value = { title: props.episode.title, summary: props.episode.summary }
  error.value = null
  editing.value = true
  open.value = true
}
async function save() {
  saving.value = true
  error.value = null
  try {
    const body: { summary: string; title?: string } = { summary: draft.value.summary }
    if (draft.value.title.trim()) body.title = draft.value.title
    await api.putEpisode(props.chatId, props.episode.id, body)
    editing.value = false
    toast('情节已保存')
    for (const k of ['episodes', 'archive', 'memory']) qc.invalidateQueries({ queryKey: [k, props.chatId] })
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="episode">
    <button class="head" type="button" @click="open = !open">
      <BookOpen />
      <span class="grow ellipsis"><strong>{{ episode.title || '未命名情节' }}</strong></span>
      <span class="badge accent">第 {{ startNo ?? '?' }}–{{ endNo ?? '?' }} 回合</span>
    </button>
    <div v-if="open" class="body">
      <template v-if="editing">
        <div class="field"><label>标题（最多 20 字）</label><input v-model="draft.title" class="input" maxlength="20" /></div>
        <div class="field"><label>摘要</label><textarea v-model="draft.summary" class="textarea" rows="7" /></div>
        <ErrorBox v-if="error" :error="error" title="保存失败" />
        <div class="row">
          <span class="spacer" />
          <button class="btn small" type="button" @click="editing = false">取消</button>
          <button class="btn primary small" type="button" :disabled="saving || !draft.summary.trim()" @click="save">保存</button>
        </div>
      </template>
      <template v-else>
        <p class="text">{{ episode.summary }}</p>
        <div v-if="editable" class="row"><span class="spacer" /><button class="btn ghost small" type="button" @click="start"><Pencil /> 编辑</button></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.episode { border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border)); border-radius: var(--radius-m); background: var(--accent-soft); overflow: hidden; }
.head { display: flex; align-items: center; gap: var(--space-2); width: 100%; padding: var(--space-2) var(--space-3); border: 0; background: none; color: inherit; font: inherit; cursor: pointer; text-align: left; }
.head svg { width: 16px; height: 16px; color: var(--accent); flex-shrink: 0; }
.body { display: flex; flex-direction: column; gap: var(--space-2); padding: 0 var(--space-3) var(--space-3); }
.text { white-space: pre-wrap; font-size: var(--text-sm); line-height: 1.7; }
</style>
