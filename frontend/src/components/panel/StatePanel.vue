<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Code2, Lock, MapPin, Pencil, Save, Undo2 } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import InfoTip from '../InfoTip.vue'
import { jsonProblem } from '../editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { formatTime, pretty } from '@/lib/format'
import { planStateDisplay } from '@/lib/stateDisplay'
import StateItems from './StateItems.vue'

const props = defineProps<{ chatId: string; editable: boolean }>()
const qc = useQueryClient()
const state = useQuery({ queryKey: computed(() => ['state', props.chatId]), queryFn: () => api.state(props.chatId) })
const schema = useQuery({ queryKey: computed(() => ['state-schema', props.chatId]), queryFn: () => api.stateSchema(props.chatId) })
const display = computed(() => planStateDisplay(state.data.value?.content, (schema.data.value?.json_schema ?? null) as Record<string, any> | null))

const WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
const editing = ref(false)
const showRaw = ref(false)

/** `2026-10-19` reads as `2026 年 10 月 19 日`; anything else is shown as written. */
function longDate(date: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  return m ? `${m[1]} 年 ${Number(m[2])} 月 ${Number(m[3])} 日` : date
}
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
      <h3>当前状态</h3>
      <span v-if="state.data.value" class="faint stamp" :title="formatTime(state.data.value.created_at)">
        {{ state.data.value.round_id ? formatTime(state.data.value.created_at) : '开场' }}
      </span>
      <span class="grow" />
      <template v-if="!editing">
        <button
          class="btn ghost icon small" type="button" :class="{ on: showRaw }" :disabled="!state.data.value"
          title="原始数据" aria-label="原始数据" :aria-pressed="showRaw" @click="showRaw = !showRaw"
        ><Code2 /></button>
        <button v-if="editable" class="btn small" type="button" :disabled="!state.data.value" @click="start"><Pencil /> 编辑</button>
        <span v-else class="locked faint" title="这一回合整理完成后才能编辑"><Lock /></span>
      </template>
      <template v-else>
        <InfoTip>保存后会按角色规则校验，并用于下一次写作。已生成的摘要不会重算。</InfoTip>
        <button class="btn small" type="button" @click="cancel"><Undo2 /> 取消</button>
        <button class="btn small primary" type="button" :disabled="saving || !parsed" @click="save"><Save /> 保存</button>
      </template>
    </div>
    <ErrorBox v-if="state.error.value" :error="state.error.value" />

    <div v-if="editing && world" class="world card card-pad">
      <div v-if="parsed" class="grid-2">
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
    </div>

    <template v-if="!editing && state.data.value">
      <section v-if="display.scene" class="scene">
        <div class="time">{{ display.scene.time }}</div>
        <div class="date">{{ [longDate(display.scene.date), display.scene.weekday].filter(Boolean).join(' · ') }}</div>
        <div class="place"><MapPin /><span>{{ display.scene.place || '未设定地点' }}</span></div>
        <StateItems v-if="display.world.length" class="world-extra" :items="display.world" />
      </section>
      <section v-for="card in display.cards" :key="card.key" class="person">
        <h4 :title="card.hint">{{ card.title }}</h4>
        <StateItems :items="card.items" />
      </section>
      <CodeEditor v-if="showRaw" :model-value="draft" language="json" readonly min-height="160px" />
    </template>
    <ul v-if="editing && worldProblems.length" class="problems">
      <li v-for="p in worldProblems" :key="p">{{ p }}</li>
    </ul>

    <CodeEditor v-if="editing" v-model="draft" language="json" min-height="260px" />
    <span v-if="editing && jsonProblem(draft)" class="bad">JSON 无效：{{ jsonProblem(draft) }}</span>
    <ErrorBox v-if="error" :error="error" title="保存失败，编辑内容已保留" />
  </div>
</template>

<style scoped>
.stamp { font-size: var(--text-xs); }
.btn.on { color: var(--accent); }
.locked { display: inline-flex; padding: var(--space-1); }
.locked svg { width: 15px; height: 15px; }
/* The scene: a large clock, the date, then the place under a hairline. */
.scene { padding: var(--space-4) var(--space-5); border-radius: 18px; background: var(--bg-sunken); color: var(--text); }
.time { font-family: var(--font-reading); font-size: 42px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.1; letter-spacing: 0.01em; }
.date { margin-top: var(--space-1-5); color: var(--text-muted); font-size: var(--text-sm); }
.place { display: flex; align-items: center; gap: var(--space-1-5); margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border); font-weight: 500; }
.place svg { width: 16px; height: 16px; flex-shrink: 0; color: var(--accent); }
.world-extra { margin-top: var(--space-2); }
.person { padding: 0 var(--space-1); }
.person h4 { margin: 0 0 var(--space-1); font-size: var(--text-md); font-weight: 600; }
.problems { margin: 0; padding-left: var(--space-5); color: var(--warn); font-size: var(--text-xs); }
.bad { font-size: var(--text-xs); color: var(--danger); }
</style>
