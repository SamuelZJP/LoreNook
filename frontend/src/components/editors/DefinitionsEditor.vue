<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { ArrowUp, ArrowDown, Plus, Trash2, Save, Eye } from 'lucide-vue-next'
import { api, type Definition } from '@/api/endpoints'
import { ApiError, isTemplateError, type TemplateErrorDetail } from '@/api/client'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import { toast } from '@/composables/toast'

/** Definitions of one owner. `base` is the owner path, e.g. `/api/characters/{id}`. */
const props = defineProps<{ base: string; chatId: string | null; title?: string }>()
const qc = useQueryClient()
const key = computed(() => ['definitions', props.base])
const list = useQuery({ queryKey: key, queryFn: () => api.definitions(props.base) })

interface Draft { content: string; enabled: boolean; has_template: boolean }
const drafts = reactive<Record<string, Draft>>({})
const errors = reactive<Record<string, unknown>>({})
const busy = ref(false)
const listError = ref<unknown>(null)
const templateError = ref<TemplateErrorDetail | null>(null)
const resolved = ref<Record<string, string> | null>(null)

watch(() => list.data.value, (defs) => {
  for (const d of defs ?? []) {
    if (!drafts[d.id]) drafts[d.id] = { content: d.content, enabled: d.enabled, has_template: d.has_template }
  }
}, { immediate: true })

function dirty(d: Definition) {
  const x = drafts[d.id]
  return !!x && (x.content !== d.content || x.enabled !== d.enabled || x.has_template !== d.has_template)
}
const anyDirty = computed(() => (list.data.value ?? []).some(dirty))

async function refresh() {
  await qc.invalidateQueries({ queryKey: key.value })
  qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
}

async function save(d: Definition) {
  const x = drafts[d.id]
  delete errors[d.id]
  try {
    const body: Record<string, unknown> = {}
    if (x.content !== d.content) body.content = x.content
    if (x.enabled !== d.enabled) body.enabled = x.enabled
    if (x.has_template !== d.has_template) body.has_template = x.has_template
    const updated = await api.patchDefinition(props.base, d.id, body)
    drafts[d.id] = { content: updated.content, enabled: updated.enabled, has_template: updated.has_template }
    await refresh()
    toast('定义已保存')
  } catch (e) {
    errors[d.id] = e
  }
}

async function saveAll() {
  for (const d of list.data.value ?? []) if (dirty(d)) await save(d)
}

async function add() {
  busy.value = true
  listError.value = null
  try {
    const order = (list.data.value?.length ?? 0)
    const created = await api.createDefinition(props.base, { content: '', enabled: true, has_template: false, order })
    drafts[created.id] = { content: '', enabled: true, has_template: false }
    await refresh()
  } catch (e) {
    listError.value = e
  } finally {
    busy.value = false
  }
}

async function remove(d: Definition) {
  if (!confirm('删除这条定义？')) return
  listError.value = null
  try {
    await api.deleteDefinition(props.base, d.id)
    delete drafts[d.id]
    await refresh()
  } catch (e) {
    listError.value = e
  }
}

async function move(index: number, delta: number) {
  const ids = (list.data.value ?? []).map((d) => d.id)
  const target = index + delta
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  listError.value = null
  try {
    qc.setQueryData(key.value, await api.reorderDefinitions(props.base, ids))
    qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
  } catch (e) {
    listError.value = e
    await refresh()
  }
}

/** Chat scope only: render all enabled definitions against the latest state. */
async function preview() {
  if (!props.chatId) return
  templateError.value = null
  resolved.value = null
  listError.value = null
  try {
    const result = await api.resolveDefinitions(props.chatId)
    const map: Record<string, string> = {}
    for (const d of [...(result.character_definitions ?? []), ...(result.user_definitions ?? [])]) map[d.id] = d.content
    resolved.value = map
  } catch (e) {
    if (e instanceof ApiError && isTemplateError(e.detail)) templateError.value = e.detail
    else listError.value = e
  }
}
</script>

<template>
  <div class="stack">
    <div class="row wrap">
      <h3 class="grow">{{ title ?? '定义' }}</h3>
      <button v-if="chatId" class="btn small" type="button" @click="preview"><Eye /> 渲染预览</button>
      <button v-if="anyDirty" class="btn small primary" type="button" @click="saveAll"><Save /> 全部保存</button>
      <button class="btn small" type="button" :disabled="busy" @click="add"><Plus /> 新增</button>
    </div>
    <p class="hint">按顺序传给预设。启用“模板”的条目会用 Jinja2 针对最新状态渲染，例如 <code v-pre>{{ state["世界"]["时间"] }}</code>。渲染失败会在调用模型前停止生成。</p>
    <ErrorBox v-if="list.error.value" :error="list.error.value" />
    <ErrorBox v-if="listError" :error="listError" />
    <div v-if="templateError" class="tpl-error">
      模板渲染失败：条目 #{{ (list.data.value ?? []).findIndex((d) => d.id === templateError!.definition_id) + 1 }}
      <span v-if="templateError.line">第 {{ templateError.line }} 行</span>：{{ templateError.message }}
    </div>
    <div v-if="resolved" class="hint ok">渲染成功，结果已显示在各启用条目下方（仅预览，不会保存）。</div>
    <div v-if="list.data.value && !list.data.value.length" class="empty">暂无定义</div>

    <div v-for="(d, i) in list.data.value" :key="d.id" class="def card" :class="{ disabled: !drafts[d.id]?.enabled, err: templateError?.definition_id === d.id }">
      <template v-if="drafts[d.id]">
        <div class="row wrap head">
          <span class="badge">#{{ i + 1 }}</span>
          <label class="check"><input v-model="drafts[d.id].enabled" type="checkbox" /> 启用</label>
          <label class="check"><input v-model="drafts[d.id].has_template" type="checkbox" /> 模板</label>
          <span class="spacer" />
          <button class="btn ghost icon small" type="button" title="上移" :disabled="i === 0" @click="move(i, -1)"><ArrowUp /></button>
          <button class="btn ghost icon small" type="button" title="下移" :disabled="i === list.data.value!.length - 1" @click="move(i, 1)"><ArrowDown /></button>
          <button class="btn ghost icon small danger" type="button" title="删除" @click="remove(d)"><Trash2 /></button>
        </div>
        <CodeEditor
          :key="`${d.id}-${drafts[d.id].has_template}`" v-model="drafts[d.id].content"
          :language="drafts[d.id].has_template ? 'jinja' : 'text'" min-height="80px" max-height="50vh"
          :error-line="templateError?.definition_id === d.id ? templateError.line : null"
        />
        <ErrorBox v-if="errors[d.id]" :error="errors[d.id]" title="保存失败" />
        <div v-if="resolved && resolved[d.id] !== undefined && drafts[d.id].has_template" class="rendered">
          <div class="label">渲染结果</div>
          <pre>{{ resolved[d.id] }}</pre>
        </div>
        <div v-if="dirty(d)" class="row">
          <span class="hint">有未保存的修改</span><span class="spacer" />
          <button class="btn small" type="button" @click="drafts[d.id] = { content: d.content, enabled: d.enabled, has_template: d.has_template }">还原</button>
          <button class="btn small primary" type="button" @click="save(d)">保存</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.def { padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.def.disabled { opacity: 0.7; }
.def.err { border-color: var(--danger); }
.head { gap: 12px; }
.tpl-error { padding: 8px 12px; border-radius: var(--radius-m); background: var(--danger-soft); font-size: 13px; }
.ok { color: var(--ok); }
.rendered { padding: 8px; background: var(--ok-soft); border-radius: var(--radius-s); }
.rendered pre { font-size: 12px; max-height: 200px; overflow: auto; }
</style>
