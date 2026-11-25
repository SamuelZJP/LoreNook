<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, FileCode } from 'lucide-vue-next'
import { api, type Character } from '@/api/endpoints'
import CodeEditor from '@/components/CodeEditor.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import { toast } from '@/composables/toast'
import { statusBarApi } from '../api'
import { EXAMPLE } from '../example'
import StatusBarFrame from './StatusBarFrame.vue'

/** The "状态栏" tab of a character: its code, with a live preview. `chatId` selects the chat's copy. */
const props = defineProps<{ character: Character; chatId: string | null }>()
const qc = useQueryClient()

const code = ref('')
const loaded = ref('')
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)
const dirty = computed(() => code.value !== loaded.value)

async function load() {
  loadError.value = null
  try {
    const bar = props.chatId ? await statusBarApi.chat(props.chatId) : await statusBarApi.card(props.character.id)
    code.value = loaded.value = bar.code
  } catch (e) {
    loadError.value = e
  }
}
watch(() => [props.character.id, props.chatId], load, { immediate: true })

async function save() {
  saving.value = true
  saveError.value = null
  try {
    if (props.chatId) {
      const bar = await statusBarApi.patchChat(props.chatId, { code: code.value })
      qc.setQueryData(['status-bar', props.chatId], bar)
      loaded.value = code.value = bar.code
    } else {
      loaded.value = code.value = (await statusBarApi.putCard(props.character.id, code.value)).code
    }
    toast('状态栏已保存')
  } catch (e) {
    saveError.value = e
  } finally {
    saving.value = false
  }
}
function insertExample() {
  if (!code.value.trim() || confirm('用示例覆盖当前代码？')) code.value = EXAMPLE
}

// Preview data: the chat's latest state, or the card's first opening run through its Schema.
const sample = ref<Record<string, unknown> | null>(null)
const sampleError = ref<unknown>(null)
async function loadSample() {
  sampleError.value = null
  try {
    sample.value = props.chatId
      ? (await api.state(props.chatId)).content
      : await api.previewInitialState({ state_schema: props.character.state_schema ?? '', initial_state: props.character.scenes[0]?.initial_state ?? {} })
  } catch (e) {
    sampleError.value = e
  }
}
watch(() => [props.character, props.chatId], loadSample, { immediate: true })
const previewData = computed(() => sample.value && {
  state: sample.value, round_no: null, character: { name: props.character.name }, identity: { name: '用户' },
})
</script>

<template>
  <div class="stack">
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <template v-else>
      <p class="hint">
        一段 HTML（可含 &lt;style&gt; 和 &lt;script&gt;），显示在回复底部。代码在隔离的框架中运行，不能访问 LoreNook，也不能发出网络请求，但可以从 CDN 加载脚本（例如 Vue）。
        用 <code>lorenook.onData(data =&gt; …)</code> 接收数据：<code>state</code>（该回合结束时的完整状态）、<code>round_no</code>、<code>character.name</code>、<code>identity.name</code>、<code>theme</code>。
        框架里可以直接使用 <code>var(--page-text)</code> 等界面颜色变量。留空表示没有状态栏。
      </p>
      <div class="row">
        <span class="spacer" />
        <button class="btn small" type="button" @click="insertExample"><FileCode /> 插入示例</button>
      </div>
      <CodeEditor v-model="code" language="html" min-height="220px" />
      <div class="stack tight">
        <h3>预览</h3>
        <span class="hint">{{ chatId ? '使用本聊天的最新状态。' : '使用第一个开场的初始状态。' }}</span>
        <ErrorBox v-if="sampleError" :error="sampleError" title="无法生成预览数据" />
        <div v-else-if="code.trim() && previewData" class="page-surface preview">
          <StatusBarFrame :code="code" :data="previewData" />
        </div>
      </div>
      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row">
        <span class="spacer" />
        <button class="btn" type="button" :disabled="!dirty" @click="code = loaded">还原</button>
        <button class="btn primary" type="button" :disabled="!dirty || saving" @click="save"><Save /> 保存状态栏</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.preview { padding: var(--space-3) var(--space-4); border: 1px solid var(--page-border); border-radius: var(--radius-l); }
</style>
