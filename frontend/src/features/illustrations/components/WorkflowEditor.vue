<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2 } from 'lucide-vue-next'
import { pretty } from '@/lib/format'
import ErrorBox from '@/components/ErrorBox.vue'
import ScopeNote from '@/components/editors/ScopeNote.vue'
import JsonField, { jsonProblem } from '@/components/editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { illustrationApi, type ImageWorkflow } from '../api'
import { MAX_IMAGES, placeholders } from '../lib'

const props = defineProps<{ id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()
const scope = computed(() => ({ chatId: props.chatId }))

const original = ref<ImageWorkflow | null>(null)
const form = ref({ name: '', base_url: 'http://127.0.0.1:8188', width: 1344, height: 768 })
const workflow = ref('{}')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

function reset(w: ImageWorkflow | null) {
  original.value = w
  if (w) {
    form.value = { name: w.name, base_url: w.base_url, width: w.width, height: w.height }
    workflow.value = pretty(w.workflow)
  } else {
    form.value = { name: '', base_url: 'http://127.0.0.1:8188', width: 1344, height: 768 }
    workflow.value = '{}'
  }
}

watch(() => [props.id, props.chatId], async () => {
  loadError.value = null
  saveError.value = null
  if (!props.id) return reset(null)
  try {
    const w = (await illustrationApi.workflows(scope.value)).find((x) => x.id === props.id)
    if (!w) throw new Error('图像工作流不存在或不属于当前范围')
    reset(w)
  } catch (e) {
    loadError.value = e
  }
}, { immediate: true })

const parsed = computed(() => (jsonProblem(workflow.value) ? null : JSON.parse(workflow.value)))
const found = computed(() => (parsed.value ? placeholders(parsed.value) : { hasPrompt: false, unknown: [] }))
/** A UI-format export has `nodes` and `links`; the API format is a map of node id to node. */
const uiFormat = computed(() => !!parsed.value && Array.isArray(parsed.value.nodes))
const fixedSize = computed(() => !!parsed.value && !uiFormat.value && !/\{\{\s*(width|height)\s*\}\}/.test(workflow.value))
const sizeOk = computed(() => [form.value.width, form.value.height].every((n) => Number.isInteger(n) && n >= 64 && n <= 8192))
const valid = computed(() => !!form.value.name.trim() && !!form.value.base_url.trim() && !!parsed.value && !uiFormat.value && found.value.hasPrompt && !found.value.unknown.length && sizeOk.value)

async function save() {
  if (!valid.value) return
  saving.value = true
  saveError.value = null
  try {
    let saved: ImageWorkflow
    if (!original.value) {
      saved = await illustrationApi.createWorkflow(scope.value, { ...form.value, workflow: parsed.value })
    } else {
      const o = original.value
      const body: Record<string, unknown> = {}
      for (const k of ['name', 'base_url', 'width', 'height'] as const) if (form.value[k] !== o[k]) body[k] = form.value[k]
      if (JSON.stringify(parsed.value) !== JSON.stringify(o.workflow)) body.workflow = parsed.value
      saved = await illustrationApi.patchWorkflow(scope.value, o.id, body)
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
    await illustrationApi.deleteWorkflow(scope.value, original.value.id)
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
      <p v-if="fixedSize" class="warn-note">工作流没有使用 <code v-pre>{{width}}</code> <code v-pre>{{height}}</code>。请确认上面的宽高与实际输出一致，否则插图的预留比例会不对。</p>
      <div class="hint stack tight">
        <span>在 ComfyUI 中使用 “Save (API Format)” 导出，再把需要替换的字符串改成占位符。</span>
        <span><code v-pre>{{prompt}}</code> 必填：本回合的用户输入、剧情内容、状态信息、人物外貌和中心人物。LoreNook 不改写它，提示词由工作流自己生成，比如接入提示词增强节点。</span>
        <span><code v-pre>{{images}}</code> 可选：已上传的参考图，主要人物在前，最多 {{ MAX_IMAGES }} 张，序号与提示词中的“参考图：图 N”对应。值是字符串形式的 JSON 数组，没有参考图时为 <code>[]</code>，适合接入接受这种输入的节点。</span>
        <span><code v-pre>{{seed}}</code> <code v-pre>{{width}}</code> <code v-pre>{{height}}</code> 是数字。ComfyUI 会缓存输入不变的节点，所以提示词增强节点也要用 <code v-pre>{{seed}}</code>，否则重新生成时提示词不变。</span>
      </div>
      <p v-if="uiFormat" class="bad">这是界面格式的工作流（含 nodes / links），请改用 API 格式导出。</p>
      <template v-else-if="parsed">
        <p v-if="!found.hasPrompt" class="bad">缺少 <code v-pre>{{prompt}}</code> 占位符。</p>
        <p v-if="found.unknown.length" class="bad">不支持的占位符：<code v-for="name in found.unknown" :key="name" class="unknown">{{ name }}</code></p>
      </template>

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
.unknown { margin-left: var(--space-1-5); }
.bad { font-size: var(--text-xs); color: var(--danger); }
.warn-note { font-size: var(--text-xs); color: var(--warn); }
</style>
