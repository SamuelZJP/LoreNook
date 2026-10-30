<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2 } from 'lucide-vue-next'
import { pretty } from '@/lib/format'
import CodeEditor from '@/components/CodeEditor.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ScopeNote from '@/components/editors/ScopeNote.vue'
import JsonField, { jsonProblem } from '@/components/editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { illustrationApi, type ImageWorkflow } from '../api'
import { placeholders } from '../lib'

const props = defineProps<{ id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()
const scope = computed(() => ({ chatId: props.chatId }))

const original = ref<ImageWorkflow | null>(null)
const form = ref({ name: '', base_url: 'http://127.0.0.1:8188', prompt_template: '', width: 1344, height: 768 })
const workflow = ref('{}')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

function reset(w: ImageWorkflow | null) {
  original.value = w
  if (w) {
    form.value = { name: w.name, base_url: w.base_url, prompt_template: w.prompt_template, width: w.width, height: w.height }
    workflow.value = pretty(w.workflow)
  } else {
    form.value = { name: '', base_url: 'http://127.0.0.1:8188', prompt_template: '', width: 1344, height: 768 }
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
const found = computed(() => (parsed.value ? placeholders(parsed.value) : { fields: [], images: [] }))
const fields = computed(() => found.value.fields)
const images = computed(() => found.value.images)

const templates = useQuery({ queryKey: ['illustration-default-templates'], queryFn: illustrationApi.defaultTemplates, staleTime: Infinity })
function insertTemplate(kind: 'text_to_image' | 'image_to_image') {
  const source = templates.data.value?.[kind]
  if (!source) return
  if (!form.value.prompt_template.trim() || confirm('用默认模板覆盖当前模板？')) form.value.prompt_template = source
}
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
      saved = await illustrationApi.createWorkflow(scope.value, { ...form.value, workflow: parsed.value })
    } else {
      const o = original.value
      const body: Record<string, unknown> = {}
      for (const k of ['name', 'base_url', 'prompt_template', 'width', 'height'] as const) if (form.value[k] !== o[k]) body[k] = form.value[k]
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
      <div class="hint stack tight">
        <span>在 ComfyUI 中使用 “Save (API Format)” 导出。在需要替换的字符串里写占位符，例如把正向提示词改成 <code v-pre>"masterpiece, {{prompt}}"</code>，把种子改成 <code v-pre>"{{seed}}"</code>。</span>
        <span><code v-pre>{{seed}}</code> <code v-pre>{{width}}</code> <code v-pre>{{height}}</code> 由 LoreNook 填入；其余占位符都是需要模型输出的提示词字段。</span>
        <span>图生图：把 LoadImage 节点的图片改成 <code v-pre>"{{image:focus_1}}"</code>、<code v-pre>"{{image:focus_2}}"</code>，对应第 1、2 位主要人物的参考图。缺少参考图时该次生成会报错。</span>
      </div>
      <p v-if="uiFormat" class="bad">这是界面格式的工作流（含 nodes / links），请改用 API 格式导出。</p>
      <div v-else-if="parsed" class="row wrap fields">
        <span class="label">提示词字段</span>
        <code v-for="f in fields" :key="f" class="badge accent">{{ f }}</code>
        <span v-if="!fields.length" class="bad">尚未找到占位符，至少需要一个，例如 <code v-pre>{{prompt}}</code></span>
        <span class="badge" :class="images.length ? 'ok' : ''">{{ images.length ? `图生图 · ${images.length} 张参考图` : '文生图' }}</span>
      </div>

      <div class="field">
        <div class="row wrap">
          <label class="label grow">提示词模板（Jinja2）</label>
          <button class="btn small" type="button" :disabled="!templates.data.value" @click="insertTemplate('text_to_image')">载入文生图默认</button>
          <button class="btn small" type="button" :disabled="!templates.data.value" @click="insertTemplate('image_to_image')">载入图生图默认</button>
        </div>
        <CodeEditor v-model="form.prompt_template" min-height="200px" max-height="50vh" />
        <span class="hint">写给提示词模型的完整内容：这个工作流要哪种语言、标签还是自然语言、每个字段写什么。留空时使用对应类型的默认模板。输出格式由系统自动追加。</span>
        <details class="vars">
          <summary class="label">可用变量</summary>
          <ul class="hint">
            <li><code v-pre>{{ focus }}</code> 主要人物，<code v-pre>{{ others }}</code> 其他人物：每项有 <code>name</code>、<code>appearance</code></li>
            <li><code v-pre>{{ char }}</code> <code v-pre>{{ user }}</code> 角色卡和用户身份的名字</li>
            <li><code v-pre>{{ state }}</code> 本回合结束时的状态（如 <code v-pre>{{ state["世界"]["地点"] }}</code>），<code v-pre>{{ state_yaml }}</code> 同一内容的 YAML</li>
            <li><code v-pre>{{ round.content }}</code> 正文，<code v-pre>{{ round.user_input }}</code> 用户输入，<code v-pre>{{ round.summary }}</code> 摘要，<code v-pre>{{ round.no }}</code> 回合号</li>
            <li><code v-pre>{{ definitions.character }}</code> <code v-pre>{{ definitions.user }}</code> 渲染后的定义（列表）</li>
            <li><code v-pre>{{ fields }}</code> 提示词字段，<code v-pre>{{ image_inputs }}</code> 图像占位符，<code v-pre>{{ width }}</code> <code v-pre>{{ height }}</code></li>
          </ul>
        </details>
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
.vars { margin-top: 4px; }
.vars summary { cursor: pointer; }
.vars ul { margin: 6px 0 0; padding-left: 18px; display: flex; flex-direction: column; gap: 3px; }
.fields { gap: 6px; }
.bad { font-size: 12px; color: var(--danger); }
</style>
