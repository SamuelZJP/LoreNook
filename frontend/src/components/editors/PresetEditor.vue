<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2, FileCode, Hammer, ScanText, Send, Download } from 'lucide-vue-next'
import { api, type Preset, type BuiltRequest } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import OutputView from '../chat/OutputView.vue'
import ScopeNote from './ScopeNote.vue'
import JsonField, { jsonProblem } from './JsonField.vue'
import { toast } from '@/composables/toast'
import { pretty, substituteNames } from '@/lib/format'
import presetExample from '@examples/presets/examples/google_tool.js?raw'

const props = defineProps<{ id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()
const scope = computed(() => ({ chatId: props.chatId }))

const original = ref<Preset | null>(null)
const name = ref('')
const source = ref('')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

watch(() => [props.id, props.chatId], async () => {
  loadError.value = null
  saveError.value = null
  if (!props.id) {
    original.value = null
    name.value = ''
    source.value = presetExample
    return
  }
  try {
    const list = await api.presets(scope.value)
    const p = list.find((x) => x.id === props.id)
    if (!p) throw new Error('预设不存在或不属于当前范围')
    original.value = p
    name.value = p.name
    source.value = p.source
  } catch (e) {
    loadError.value = e
  }
}, { immediate: true })

const dirty = computed(() => !original.value || original.value.name !== name.value || original.value.source !== source.value)

async function save() {
  saving.value = true
  saveError.value = null
  try {
    let saved: Preset
    if (!original.value) saved = await api.createPreset(scope.value, { name: name.value, source: source.value })
    else {
      const body: { name?: string; source?: string } = {}
      if (name.value !== original.value.name) body.name = name.value
      if (source.value !== original.value.source) body.source = source.value
      saved = await api.patchPreset(scope.value, original.value.id, body)
    }
    original.value = saved
    qc.invalidateQueries({ queryKey: ['presets', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('预设已保存')
    emit('saved', saved.id)
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!original.value || !confirm('删除这个预设？')) return
  try {
    await api.deletePreset(scope.value, original.value.id)
    qc.invalidateQueries({ queryKey: ['presets', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('已删除')
    emit('deleted')
  } catch (e) {
    saveError.value = e
  }
}

function fillExample() {
  if (source.value === presetExample || confirm('用示例覆盖当前源码？')) source.value = presetExample
}

// ---- Trials (run against the saved source) ----
const sampleMaterials = {
  first_message: '<content>开场消息</content>',
  character_name: '角色',
  user_identity_name: '我',
  character_definitions: [{ id: 'def-1', order: 0, content: '角色设定' }],
  user_definitions: [],
  memory: '',
  recent_rounds: [{ id: 'round-1', round_no: 1, user_input: '你好', ai_output: '<content>你好呀。</content>' }],
  user_input: '今天做什么？',
  state: { 世界: { 日期: '2026-10-19', 星期: '星期一', 时间: '08:00', 地点: '家' } },
}
const materials = ref(pretty(sampleMaterials))
const built = ref<BuiltRequest | null>(null)
const builtText = ref('')
const trialError = ref<unknown>(null)
const trialBusy = ref<string | null>(null)
const responseText = ref(pretty({
  candidates: [{ finishReason: 'STOP', content: { role: 'model', parts: [{ functionCall: { name: 'game_content', args: { content: '<report_nya~>报告</report_nya~>\n<content>正文</content>' } } }] } }],
}))
const parsed = ref<string | null>(null)
const invokeModelId = ref('')

const models = useQuery({ queryKey: computed(() => ['models', props.chatId]), queryFn: () => api.models(scope.value) })

async function trial<T>(label: string, fn: () => Promise<T>) {
  trialBusy.value = label
  trialError.value = null
  try {
    return await fn()
  } catch (e) {
    trialError.value = e
    return undefined
  } finally {
    trialBusy.value = null
  }
}

/** Chat scope: assemble the same materials the writing workflow would use. */
async function loadChatMaterials() {
  const chatId = props.chatId
  if (!chatId) return
  await trial('materials', async () => {
    const [chat, defs, memory] = await Promise.all([api.chat(chatId), api.resolveDefinitions(chatId), api.memoryMaterials(chatId)])
    materials.value = pretty({
      first_message: substituteNames(chat.character.scenes[0]?.first_message ?? '', chat.user_identity.name, chat.character.name),
      character_name: chat.character.name,
      user_identity_name: chat.user_identity.name,
      character_definitions: defs.character_definitions,
      user_definitions: defs.user_definitions,
      ...memory,
      user_input: '',
      state: chat.latest_state.content,
    })
  })
}

async function runBuild() {
  if (!original.value) return
  const result = await trial('build', () => api.buildPreset(scope.value, original.value!.id, JSON.parse(materials.value)))
  if (result) {
    built.value = result
    builtText.value = pretty(result)
  }
}
async function runInvoke() {
  if (!invokeModelId.value || jsonProblem(builtText.value)) return
  const result = await trial('invoke', () => api.invokeModel(scope.value, invokeModelId.value, JSON.parse(builtText.value)))
  if (result) responseText.value = pretty(result.response)
}
async function runParse() {
  if (!original.value) return
  const result = await trial('parse', () => api.parsePreset(scope.value, original.value!.id, JSON.parse(responseText.value)))
  if (result) parsed.value = result.ai_output
}
</script>

<template>
  <div class="stack">
    <ScopeNote :chat-id="chatId" what="预设" />
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else>
      <div class="field"><label>名称</label><input v-model="name" class="input" /></div>
      <div class="field">
        <div class="row">
          <label class="label grow">JavaScript 源码</label>
          <button class="btn small" type="button" @click="fillExample"><FileCode /> 填入示例</button>
        </div>
        <CodeEditor v-model="source" language="javascript" min-height="320px" />
        <span class="hint">定义同步函数 <code>build(materials)</code> 返回 <code>{api_type, body}</code>，以及 <code>parse(response)</code> 返回完整 AI 输出文本。不要使用 import/export。</span>
      </div>
      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row">
        <button v-if="original" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <button class="btn primary" type="button" :disabled="saving || !name.trim() || !dirty" @click="save"><Save /> {{ original ? '保存' : '创建' }}</button>
      </div>

      <details v-if="original" class="trials card card-pad" open>
        <summary><h3>试运行</h3></summary>
        <div class="stack">
          <p class="hint">试运行使用<strong>已保存</strong>的源码，不会修改任何记录。{{ dirty ? '当前有未保存的修改。' : '' }}</p>
          <div class="row wrap">
            <span class="label grow">1. 构建（build）素材</span>
            <button v-if="chatId" class="btn small" type="button" :disabled="!!trialBusy" @click="loadChatMaterials"><Download /> 用当前聊天素材</button>
          </div>
          <JsonField v-model="materials" min-height="140px" />
          <div class="row"><span class="spacer" />
            <button class="btn small" type="button" :disabled="!!trialBusy || !!jsonProblem(materials)" @click="runBuild"><Hammer /> {{ trialBusy === 'build' ? '构建中…' : '运行 build' }}</button>
          </div>
          <JsonField v-if="built" v-model="builtText" label="构建结果（可编辑后用于模型测试）" min-height="140px" />

          <div v-if="built" class="row wrap">
            <span class="label grow">2. 可选：用模型实际调用一次</span>
            <select v-model="invokeModelId" class="select model-pick">
              <option value="">选择模型配置</option>
              <option v-for="m in models.data.value" :key="m.id" :value="m.id">{{ m.name }} · {{ m.api_type }}</option>
            </select>
            <button class="btn small" type="button" :disabled="!!trialBusy || !invokeModelId" @click="runInvoke"><Send /> {{ trialBusy === 'invoke' ? '调用中…' : '调用' }}</button>
          </div>

          <span class="label">3. 解析（parse）模型响应</span>
          <JsonField v-model="responseText" min-height="140px" />
          <div class="row"><span class="spacer" />
            <button class="btn small" type="button" :disabled="!!trialBusy || !!jsonProblem(responseText)" @click="runParse"><ScanText /> {{ trialBusy === 'parse' ? '解析中…' : '运行 parse' }}</button>
          </div>
          <ErrorBox v-if="trialError" :error="trialError" title="试运行失败" />
          <div v-if="parsed !== null" class="stack tight">
            <span class="label">解析结果（显示效果）</span>
            <div class="card card-pad page-surface"><OutputView :text="parsed" /></div>
            <details><summary class="label">原文</summary><pre class="raw">{{ parsed }}</pre></details>
          </div>
        </div>
      </details>
    </template>
  </div>
</template>

<style scoped>
.trials summary { cursor: pointer; margin-bottom: 8px; }
.trials summary h3 { display: inline; }
.model-pick { width: auto; max-width: 100%; }
.raw { padding: 8px; background: var(--bg-sunken); border-radius: var(--radius-s); font-size: 12px; }
</style>
