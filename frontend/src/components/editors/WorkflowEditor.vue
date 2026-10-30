<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2 } from 'lucide-vue-next'
import { api, type ImageWorkflow } from '@/api/endpoints'
import { promptFields } from '@/lib/illustrations'
import { pretty } from '@/lib/format'
import ErrorBox from '../ErrorBox.vue'
import ScopeNote from './ScopeNote.vue'
import JsonField, { jsonProblem } from './JsonField.vue'
import { toast } from '@/composables/toast'

const props = defineProps<{ id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()
const scope = computed(() => ({ chatId: props.chatId }))

const INSTRUCTIONS = `prompt：英文 danbooru 风格标签，逗号分隔。先写人物数量、外貌、衣着、动作、表情，再写场景、光线和镜头。
negative_prompt：英文标签，写需要避免的内容，例如 lowres, bad hands, extra fingers。`

const original = ref<ImageWorkflow | null>(null)
const form = ref({ name: '', base_url: 'http://127.0.0.1:8188', instructions: INSTRUCTIONS, width: 1344, height: 768 })
const workflow = ref('{}')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

function reset(w: ImageWorkflow | null) {
  original.value = w
  if (w) {
    form.value = { name: w.name, base_url: w.base_url, instructions: w.instructions, width: w.width, height: w.height }
    workflow.value = pretty(w.workflow)
  } else {
    form.value = { name: '', base_url: 'http://127.0.0.1:8188', instructions: INSTRUCTIONS, width: 1344, height: 768 }
    workflow.value = '{}'
  }
}

watch(() => [props.id, props.chatId], async () => {
  loadError.value = null
  saveError.value = null
  if (!props.id) return reset(null)
  try {
    const w = (await api.workflows(scope.value)).find((x) => x.id === props.id)
    if (!w) throw new Error('图像工作流不存在或不属于当前范围')
    reset(w)
  } catch (e) {
    loadError.value = e
  }
}, { immediate: true })

const parsed = computed(() => (jsonProblem(workflow.value) ? null : JSON.parse(workflow.value)))
const fields = computed(() => (parsed.value ? promptFields(parsed.value) : []))
/** A UI-format export has `nodes` and `links`; the API format is a map of node id to node. */
const uiFormat = computed(() => !!parsed.value && Array.isArray(parsed.value.nodes))
const sizeOk = computed(() => [form.value.width, form.value.height].every((n) => Number.isInteger(n) && n >= 64 && n <= 8192))
const valid = computed(() => !!form.value.name.trim() && !!form.value.base_url.trim() && !!parsed.value && !uiFormat.value && fields.value.length > 0 && sizeOk.value)

async function save() {
  if (!valid.value) return
  saving.value = true
  saveError.value = null
  try {
    let saved: ImageWorkflow
    if (!original.value) {
      saved = await api.createWorkflow(scope.value, { ...form.value, workflow: parsed.value })
    } else {
      const o = original.value
      const body: Record<string, unknown> = {}
      for (const k of ['name', 'base_url', 'instructions', 'width', 'height'] as const) if (form.value[k] !== o[k]) body[k] = form.value[k]
      if (JSON.stringify(parsed.value) !== JSON.stringify(o.workflow)) body.workflow = parsed.value
      saved = await api.patchWorkflow(scope.value, o.id, body)
    }
    reset(saved)
    qc.invalidateQueries({ queryKey: ['workflows', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('图像工作流已保存')
    emit('saved', saved.id)
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!original.value || !confirm('删除这个图像工作流？已生成的插图会保留。')) return
  try {
    await api.deleteWorkflow(scope.value, original.value.id)
    qc.invalidateQueries({ queryKey: ['workflows', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('已删除')
    emit('deleted')
  } catch (e) {
    saveError.value = e
  }
}
</script>

<template>
  <div class="stack">
    <ScopeNote :chat-id="chatId" what="图像工作流" />
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else>
      <div class="grid-2">
        <div class="field"><label>名称</label><input v-model="form.name" class="input" /></div>
        <div class="field">
          <label>ComfyUI 地址</label>
          <input v-model="form.base_url" class="input mono" placeholder="http://127.0.0.1:8188" />
        </div>
      </div>
      <div class="grid-2">
        <div class="field"><label>宽度</label><input v-model.number="form.width" class="input" type="number" min="64" max="8192" /></div>
        <div class="field"><label>高度</label><input v-model.number="form.height" class="input" type="number" min="64" max="8192" /></div>
      </div>
      <p class="hint">尺寸填入 <code v-pre>{{width}}</code> <code v-pre>{{height}}</code>，也决定聊天中插图的预留比例。</p>

      <JsonField v-model="workflow" label="工作流（API 格式）" min-height="200px" />
      <div class="hint stack tight">
        <span>在 ComfyUI 中使用 “Save (API Format)” 导出。在需要替换的字符串里写占位符，例如把正向提示词改成 <code v-pre>"masterpiece, {{prompt}}"</code>，把种子改成 <code v-pre>"{{seed}}"</code>。</span>
        <span><code v-pre>{{seed}}</code> <code v-pre>{{width}}</code> <code v-pre>{{height}}</code> 由 LoreNook 填入；其余占位符都是需要模型输出的提示词字段。</span>
      </div>
      <p v-if="uiFormat" class="bad">这是界面格式的工作流（含 nodes / links），请改用 API 格式导出。</p>
      <div v-else-if="parsed" class="row wrap fields">
        <span class="label">提示词字段</span>
        <code v-for="f in fields" :key="f" class="badge accent">{{ f }}</code>
        <span v-if="!fields.length" class="bad">尚未找到占位符，至少需要一个，例如 <code v-pre>{{prompt}}</code></span>
      </div>

      <div class="field">
        <label>提示词要求</label>
        <textarea v-model="form.instructions" class="textarea" rows="6" />
        <span class="hint">告诉模型这个工作流需要怎样的提示词：语言、标签格式、每个字段写什么。可以使用 <code v-pre>{{char}}</code> <code v-pre>{{user}}</code>。</span>
      </div>

      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row">
        <button v-if="original" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <button class="btn primary" type="button" :disabled="saving || !valid" @click="save"><Save /> {{ original ? '保存' : '创建' }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fields { gap: 6px; }
.bad { font-size: 12px; color: var(--danger); }
</style>
