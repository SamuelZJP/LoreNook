<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2, Send, KeyRound } from 'lucide-vue-next'
import { api, API_TYPES, type ModelConfig } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'
import ScopeNote from './ScopeNote.vue'
import JsonField, { jsonProblem } from './JsonField.vue'
import { toast } from '@/composables/toast'
import { pretty } from '@/lib/format'

const props = defineProps<{ id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()
const scope = computed(() => ({ chatId: props.chatId }))

const DEFAULTS: Record<string, { base_url: string; params: object; test: object }> = {
  google_generate_content: {
    base_url: 'https://generativelanguage.googleapis.com/v1beta',
    params: { generationConfig: { temperature: 0.8 } },
    test: { contents: [{ role: 'user', parts: [{ text: '请用一句话打个招呼。' }] }] },
  },
  deepseek_chat_completions: {
    base_url: 'https://api.deepseek.com',
    params: { temperature: 0.7, max_tokens: 4096, stream: false },
    test: { messages: [{ role: 'user', content: '请用一句话打个招呼。' }], stream: false },
  },
}

const original = ref<ModelConfig | null>(null)
const form = ref({ name: '', api_type: 'deepseek_chat_completions', base_url: '', model: '' })
const params = ref('{}')
/** Credential intent: never send `api_key` unless the user chose to replace or clear it. */
const keyMode = ref<'keep' | 'replace' | 'clear'>('keep')
const keyInput = ref('')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

function reset(m: ModelConfig | null) {
  original.value = m
  keyMode.value = m ? 'keep' : 'replace'
  keyInput.value = ''
  if (m) {
    form.value = { name: m.name, api_type: m.api_type, base_url: m.base_url, model: m.model }
    params.value = pretty(m.default_parameters)
  } else {
    const d = DEFAULTS.deepseek_chat_completions
    form.value = { name: '', api_type: 'deepseek_chat_completions', base_url: d.base_url, model: '' }
    params.value = pretty(d.params)
  }
  testBody.value = pretty(DEFAULTS[form.value.api_type]?.test ?? {})
}

watch(() => [props.id, props.chatId], async () => {
  loadError.value = null
  saveError.value = null
  if (!props.id) return reset(null)
  try {
    const m = (await api.models(scope.value)).find((x) => x.id === props.id)
    if (!m) throw new Error('模型配置不存在或不属于当前范围')
    reset(m)
  } catch (e) {
    loadError.value = e
  }
}, { immediate: true })

function onTypeChange() {
  const d = DEFAULTS[form.value.api_type]
  if (!d) return
  if (!original.value) {
    form.value.base_url = d.base_url
    params.value = pretty(d.params)
  }
  testBody.value = pretty(d.test)
}

const customType = computed(() => !(API_TYPES as readonly string[]).includes(form.value.api_type))

async function save() {
  if (jsonProblem(params.value)) return
  saving.value = true
  saveError.value = null
  try {
    const default_parameters = JSON.parse(params.value)
    let saved: ModelConfig
    if (!original.value) {
      saved = await api.createModel(scope.value, { ...form.value, default_parameters, api_key: keyMode.value === 'replace' ? keyInput.value : '' })
    } else {
      const o = original.value
      const body: Record<string, unknown> = {}
      for (const k of ['name', 'api_type', 'base_url', 'model'] as const) if (form.value[k] !== o[k]) body[k] = form.value[k]
      if (JSON.stringify(default_parameters) !== JSON.stringify(o.default_parameters)) body.default_parameters = default_parameters
      if (keyMode.value === 'replace' && keyInput.value) body.api_key = keyInput.value
      if (keyMode.value === 'clear') body.api_key = ''
      saved = await api.patchModel(scope.value, o.id, body)
    }
    reset(saved)
    qc.invalidateQueries({ queryKey: ['models', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('模型配置已保存')
    emit('saved', saved.id)
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!original.value || !confirm('删除这个模型配置？使用它的用途绑定也会被删除。')) return
  try {
    await api.deleteModel(scope.value, original.value.id)
    qc.invalidateQueries({ queryKey: ['models', props.chatId] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast('已删除')
    emit('deleted')
  } catch (e) {
    saveError.value = e
  }
}

// ---- Invocation test (one real call) ----
const testBody = ref('{}')
const testing = ref(false)
const testError = ref<unknown>(null)
const testResponse = ref<Record<string, unknown> | null>(null)

const testText = computed(() => {
  const r = testResponse.value as Record<string, any> | null
  if (!r) return null
  const google = r.candidates?.[0]?.content?.parts?.map((p: any) => p.text ?? (p.functionCall ? `[functionCall ${p.functionCall.name}]` : '')).join('')
  const deepseek = r.choices?.[0]?.message?.content
  return google ?? deepseek ?? null
})

async function test() {
  if (!original.value || jsonProblem(testBody.value)) return
  testing.value = true
  testError.value = null
  testResponse.value = null
  try {
    const result = await api.invokeModel(scope.value, original.value.id, { api_type: original.value.api_type, body: JSON.parse(testBody.value) })
    testResponse.value = result.response
  } catch (e) {
    testError.value = e
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="stack">
    <ScopeNote :chat-id="chatId" what="模型配置" />
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else>
      <div class="grid-2">
        <div class="field"><label>名称</label><input v-model="form.name" class="input" /></div>
        <div class="field">
          <label>API 类型</label>
          <select v-model="form.api_type" class="select" @change="onTypeChange">
            <option v-for="t in API_TYPES" :key="t" :value="t">{{ t }}</option>
            <option v-if="customType" :value="form.api_type">{{ form.api_type }}（不受支持）</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>Base URL</label>
        <input v-model="form.base_url" class="input mono" placeholder="https://…" />
        <span class="hint">API 根地址，包含所需的版本路径；不要包含模型路径、查询参数或凭据。</span>
      </div>
      <div class="field"><label>模型</label><input v-model="form.model" class="input mono" placeholder="例如 deepseek-chat" /></div>

      <div class="field">
        <label>API Key</label>
        <div v-if="original" class="row wrap key-modes">
          <span class="badge" :class="original.has_api_key ? 'ok' : ''"><KeyRound /> {{ original.has_api_key ? '已保存密钥' : '未设置密钥' }}</span>
          <label class="check"><input v-model="keyMode" type="radio" value="keep" /> 保持不变</label>
          <label class="check"><input v-model="keyMode" type="radio" value="replace" /> 替换</label>
          <label v-if="original.has_api_key" class="check"><input v-model="keyMode" type="radio" value="clear" /> 清除</label>
        </div>
        <input v-if="keyMode === 'replace'" v-model="keyInput" class="input mono" type="password" autocomplete="off" placeholder="输入新的 API Key" />
        <span v-if="keyMode === 'clear'" class="hint warn">保存时将清除已存储的密钥。</span>
      </div>

      <JsonField v-model="params" label="默认参数（使用目标 API 的原生字段，缺失的请求字段会被递归填充）" min-height="100px" />
      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row">
        <button v-if="original" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <button class="btn primary" type="button" :disabled="saving || !form.name.trim() || !form.model.trim() || !form.base_url.trim() || !!jsonProblem(params)" @click="save">
          <Save /> {{ original ? '保存' : '创建' }}
        </button>
      </div>

      <details v-if="original" class="card card-pad">
        <summary><h3>调用测试</h3></summary>
        <div class="stack">
          <p class="hint">使用已保存的配置真实调用一次模型（会消耗额度），默认参数会合并进请求体。</p>
          <JsonField v-model="testBody" label="请求体" min-height="100px" />
          <div class="row"><span class="spacer" />
            <button class="btn" type="button" :disabled="testing || !!jsonProblem(testBody)" @click="test"><Send /> {{ testing ? '调用中…' : '发送测试请求' }}</button>
          </div>
          <ErrorBox v-if="testError" :error="testError" title="调用失败" />
          <template v-if="testResponse">
            <div v-if="testText" class="card card-pad plain">{{ testText }}</div>
            <details><summary class="label">完整响应</summary><pre class="raw">{{ pretty(testResponse) }}</pre></details>
          </template>
        </div>
      </details>
    </template>
  </div>
</template>

<style scoped>
.key-modes { gap: 14px; margin-bottom: 4px; }
.key-modes svg { width: 12px; height: 12px; }
.warn { color: var(--warn); }
summary { cursor: pointer; }
summary h3 { display: inline; }
.raw { padding: 8px; background: var(--bg-sunken); border-radius: var(--radius-s); font-size: 12px; max-height: 360px; overflow: auto; }
</style>
