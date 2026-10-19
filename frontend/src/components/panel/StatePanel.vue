<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Pencil, Save, Undo2 } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import { jsonProblem } from '../editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { formatTime, pretty } from '@/lib/format'

const props = defineProps<{ chatId: string; editable: boolean }>()
const qc = useQueryClient()
const state = useQuery({ queryKey: computed(() => ['state', props.chatId]), queryFn: () => api.state(props.chatId) })

const WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const error = ref<unknown>(null)

watch(() => state.data.value, (s) => {
  if (s && !editing.value) draft.value = pretty(s.content)
}, { immediate: true })

const parsed = computed<Record<string, any> | null>(() => {
  if (jsonProblem(draft.value)) return null
  return JSON.parse(draft.value)
})
const world = computed(() => {
  const w = (editing.value ? parsed.value : state.data.value?.content)?.['世界']
  return w && typeof w === 'object' && !Array.isArray(w) ? (w as Record<string, unknown>) : null
})

/** Edit one world field through the JSON text, preserving every other value and type. */
function setWorld(key: string, value: string) {
  const obj = parsed.value
  if (!obj) return
  const w = obj['世界'] && typeof obj['世界'] === 'object' ? obj['世界'] : (obj['世界'] = {})
  w[key] = value
  draft.value = pretty(obj)
}

const worldProblems = computed(() => {
  const w = world.value
  if (!w) return ['缺少 世界 对象']
  const out: string[] = []
  const date = w['日期']
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(`${date}T00:00:00Z`)) || new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) !== date) out.push('日期 需为有效的 YYYY-MM-DD')
  if (typeof w['星期'] !== 'string' || !WEEKDAYS.includes(w['星期'])) out.push('星期 需为 星期一–星期日')
  const time = w['时间']
  if (typeof time !== 'string' || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) out.push('时间 需为 HH:mm')
  if (typeof w['地点'] !== 'string') out.push('地点 需为字符串')
  return out
})

function start() {
  draft.value = pretty(state.data.value?.content ?? {})
  error.value = null
  editing.value = true
}
function cancel() {
  editing.value = false
  error.value = null
  draft.value = pretty(state.data.value?.content ?? {})
}
async function save() {
  if (!parsed.value) return
  saving.value = true
  error.value = null
  try {
    const saved = await api.putState(props.chatId, parsed.value)
    qc.setQueryData(['state', props.chatId], saved)
    qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    editing.value = false
    draft.value = pretty(saved.content)
    const corrected = JSON.stringify(saved.content) !== JSON.stringify(parsed.value)
    toast(corrected ? '状态已保存（已按 Schema 修正）' : '状态已保存')
  } catch (e) {
    error.value = e // keep draft for correction
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3 class="grow">最新状态</h3>
      <template v-if="!editing">
        <button class="btn small" type="button" :disabled="!editable || !state.data.value" @click="start"><Pencil /> 编辑</button>
      </template>
      <template v-else>
        <button class="btn small" type="button" @click="cancel"><Undo2 /> 取消</button>
        <button class="btn small primary" type="button" :disabled="saving || !parsed" @click="save"><Save /> 保存</button>
      </template>
    </div>
    <p v-if="state.data.value" class="hint">
      {{ state.data.value.round_id ? '来自最近保存的回合' : '初始状态（尚无回合）' }} · {{ formatTime(state.data.value.created_at) }}
    </p>
    <p v-if="!editable" class="hint">归档未完成时不能手动编辑状态。</p>
    <ErrorBox v-if="state.error.value" :error="state.error.value" />

    <div v-if="world" class="world card card-pad">
      <template v-if="editing && parsed">
        <div class="grid-2">
          <div class="field"><label>日期</label><input class="input" :value="world['日期']" placeholder="YYYY-MM-DD" @input="setWorld('日期', ($event.target as HTMLInputElement).value)" /></div>
          <div class="field">
            <label>星期</label>
            <select class="select" :value="world['星期']" @change="setWorld('星期', ($event.target as HTMLSelectElement).value)">
              <option v-for="d in WEEKDAYS" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="field"><label>时间</label><input class="input" :value="world['时间']" placeholder="HH:mm" @input="setWorld('时间', ($event.target as HTMLInputElement).value)" /></div>
          <div class="field"><label>地点</label><input class="input" :value="world['地点']" @input="setWorld('地点', ($event.target as HTMLInputElement).value)" /></div>
        </div>
      </template>
      <div v-else class="row wrap chips">
        <span class="badge accent">{{ world['日期'] }} {{ world['星期'] }}</span>
        <span class="badge accent">{{ world['时间'] }}</span>
        <span class="badge">{{ world['地点'] || '（未设定地点）' }}</span>
      </div>
    </div>
    <ul v-if="editing && worldProblems.length" class="problems">
      <li v-for="p in worldProblems" :key="p">{{ p }}</li>
    </ul>

    <CodeEditor v-if="editing" v-model="draft" language="json" min-height="260px" />
    <CodeEditor v-else-if="state.data.value" :model-value="draft" language="json" readonly min-height="200px" />
    <span v-if="editing && jsonProblem(draft)" class="bad">JSON 无效：{{ jsonProblem(draft) }}</span>
    <p v-if="editing" class="hint">保存后会经过角色 Schema 校验与修正，并立即用于下一次生成；不会重新计算摘要或情节。键名需保持原样（例如 <code>世界</code>）。</p>
    <ErrorBox v-if="error" :error="error" title="保存失败，编辑内容已保留" />
  </div>
</template>

<style scoped>
.chips { gap: 6px; }
.problems { margin: 0; padding-left: 18px; color: var(--warn); font-size: 12px; }
.bad { font-size: 12px; color: var(--danger); }
</style>
