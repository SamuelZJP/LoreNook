<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Lock, MapPin, Pencil, Save, Undo2 } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import InfoTip from '../InfoTip.vue'
import { jsonProblem } from '../editors/JsonField.vue'
import { toast } from '@/composables/toast'
import { formatTime, pretty } from '@/lib/format'
import { planStateDisplay, type Item } from '@/lib/stateDisplay'
import StateItems from './StateItems.vue'
import StateChanges from './StateChanges.vue'
import { planLatestChanges } from '@/lib/stateChanges'

const props = defineProps<{ chatId: string; editable: boolean }>()
/** `roomy` while the editor or the raw data needs the panel's full height. */
const emit = defineEmits<{ roomy: [boolean] }>()
const qc = useQueryClient()
const state = useQuery({ queryKey: computed(() => ['state', props.chatId]), queryFn: () => api.state(props.chatId) })
const schema = useQuery({ queryKey: computed(() => ['state-schema', props.chatId]), queryFn: () => api.stateSchema(props.chatId) })
const jsonSchema = computed(() => (schema.data.value?.json_schema ?? null) as Record<string, any> | null)
const display = computed(() => planStateDisplay(state.data.value?.content, jsonSchema.value))

// Below the scene: the state, what the latest round changed, or the raw JSON. Not persisted on purpose.
type View = 'state' | 'changes' | 'raw'
const VIEWS: { id: View; label: string }[] = [{ id: 'state', label: '状态' }, { id: 'changes', label: '变化' }, { id: 'raw', label: '原始' }]
const view = ref<View>('state')

// The round this state belongs to; shares the chat view's cached round list.
const rounds = useQuery({ queryKey: computed(() => ['rounds', props.chatId]), queryFn: () => api.rounds(props.chatId) })
const roundLabel = computed(() => {
  const id = state.data.value?.round_id
  if (!id) return '开场'
  const no = rounds.data.value?.find((r) => r.id === id)?.round_no
  return no === undefined ? '' : `#${no}`
})

/** Extra world fields as short chips after the place; nested groups stay as rows. */
function chipText(it: Item): string | null {
  switch (it.kind) {
    case 'text': return it.value
    case 'dot': return it.value ? '是' : '否'
    case 'bar': return `${it.value}/${it.max}`
    case 'tags': return it.value.join('、')
    default: return null
  }
}
const worldChips = computed(() => display.value.world.flatMap((it) => {
  const text = chipText(it)
  return text === null ? [] : [{ key: it.key, label: it.label, hint: it.hint, text }]
}))
const worldGroups = computed(() => display.value.world.filter((it) => it.kind === 'group'))
// Keyed by the state's refresh time, so a new round or a manual save brings fresh changes.
const history = useQuery({
  queryKey: computed(() => ['state-history', props.chatId, state.dataUpdatedAt.value]),
  queryFn: () => api.stateHistory(props.chatId, 2),
  enabled: computed(() => view.value === 'changes'),
  // Keep the last result on screen while a newer one loads.
  placeholderData: (previous) => previous,
})
const latestChanges = computed(() => (history.data.value ? planLatestChanges(history.data.value, jsonSchema.value) : null))

const WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
const editing = ref(false)
const roomy = computed(() => editing.value || view.value === 'raw')
watch(roomy, (on) => emit('roomy', on))
onBeforeUnmount(() => { if (roomy.value) emit('roomy', false) })

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
  <div class="state-panel">
    <ErrorBox v-if="state.error.value" :error="state.error.value" />

    <!-- The scene, or its fields while editing -->
    <div v-if="editing && world" class="world-edit">
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
    <section v-else-if="state.data.value && display.scene" class="scene">
      <div class="time">{{ display.scene.time }}</div>
      <div class="date">{{ [longDate(display.scene.date), display.scene.weekday].filter(Boolean).join(' · ') }}</div>
      <div class="place">
        <MapPin /><span class="place-name">{{ display.scene.place || '未设定地点' }}</span>
        <span v-for="c in worldChips" :key="c.key" class="chip" :title="c.hint"><span class="chip-label">{{ c.label }}</span>{{ c.text }}</span>
      </div>
      <StateItems v-if="worldGroups.length" class="world-extra" :items="worldGroups" />
    </section>

    <!-- One toolbar: the view on the left, the round and editing on the right -->
    <div v-if="state.data.value" class="toolbar">
      <template v-if="!editing">
        <div class="switch" role="group" aria-label="显示内容">
          <button
            v-for="v in VIEWS" :key="v.id" type="button" :class="{ on: view === v.id }" :aria-pressed="view === v.id" @click="view = v.id"
          >{{ v.label }}</button>
        </div>
        <span class="grow" />
        <span class="round" :title="formatTime(state.data.value.created_at)">
          {{ view === 'changes' && latestChanges ? `#${latestChanges.roundNo} 的变化` : roundLabel }}
        </span>
        <button v-if="editable" class="btn ghost icon small tool" type="button" title="编辑状态" aria-label="编辑状态" @click="start"><Pencil /></button>
        <span v-else class="locked" title="这一回合整理完成后才能编辑"><Lock /></span>
      </template>
      <template v-else>
        <span class="editing-title">编辑{{ roundLabel === '开场' ? '开场' : ` ${roundLabel} ` }}的状态</span>
        <InfoTip>保存后会按角色规则校验，并用于下一次写作。已生成的摘要不会重算。</InfoTip>
        <span class="grow" />
        <button class="btn small" type="button" @click="cancel"><Undo2 /> 取消</button>
        <button class="btn small primary" type="button" :disabled="saving || !parsed" @click="save"><Save /> 保存</button>
      </template>
    </div>

    <template v-if="!editing && state.data.value">
      <template v-if="view === 'state'">
        <section v-for="card in display.cards" :key="card.key" class="person">
          <h4 :title="card.hint">{{ card.title }}</h4>
          <StateItems :items="card.items" />
        </section>
      </template>
      <template v-else-if="view === 'changes'">
        <ErrorBox v-if="history.error.value" :error="history.error.value" title="无法读取变化" />
        <StateChanges v-else :changes="latestChanges" :loading="history.isLoading.value" />
      </template>
      <CodeEditor v-else :model-value="draft" language="json" readonly min-height="160px" />
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
.state-panel { display: flex; flex-direction: column; gap: var(--space-3); }
/* The scene: a large clock, the date, then the place and any extra world fields as chips. */
.scene { padding: var(--space-4) var(--space-5) 14px; border-radius: 18px; background: var(--bg-sunken); color: var(--text); }
.time { font-family: var(--font-reading); font-size: 40px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.05; letter-spacing: 0.01em; }
.date { margin-top: var(--space-1-5); color: var(--text-muted); font-size: var(--text-sm); }
.place { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1-5); margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border); }
.place svg { width: 16px; height: 16px; flex-shrink: 0; color: var(--accent); }
.place-name { font-weight: 500; margin-right: var(--space-1); }
.chip { font-size: var(--text-xs); color: var(--text-muted); background: var(--bg-elev); border-radius: var(--radius-pill); padding: 1px var(--space-2); }
.chip-label { color: var(--text-faint); margin-right: 3px; }
.world-extra { margin-top: var(--space-2); }
.world-edit { padding: 14px; border-radius: 18px; background: var(--bg-sunken); }
/* The toolbar: view switch, round, edit. */
.toolbar { display: flex; align-items: center; gap: var(--space-2); min-height: 30px; padding-left: var(--space-1); }
.switch { display: inline-flex; padding: 2px; border-radius: var(--radius-s); background: var(--bg-sunken); }
.switch button {
  min-height: 26px; padding: 0 10px; border: 0; border-radius: 6px; background: none; cursor: pointer;
  font: inherit; font-size: var(--text-xs); font-weight: 500; color: var(--text-muted);
}
.switch button:hover { color: var(--text); }
.switch button.on { background: var(--bg-elev); color: var(--text); box-shadow: 0 1px 2px rgb(0 0 0 / 8%); }
.round { font-size: var(--text-xs); color: var(--text-faint); font-variant-numeric: tabular-nums; white-space: nowrap; }
.tool { background: var(--bg-sunken); border-radius: var(--radius-s); color: var(--text-muted); }
.tool svg { width: 14px; height: 14px; }
.locked { display: inline-flex; width: 30px; justify-content: center; color: var(--text-faint); }
.locked svg { width: 14px; height: 14px; }
.editing-title { font-size: var(--text-sm); font-weight: 600; }
.person { padding: 0 var(--space-1); }
.person h4 { margin: 0 0 var(--space-1); font-size: var(--text-md); font-weight: 600; }
.problems { margin: 0; padding-left: var(--space-5); color: var(--warn); font-size: var(--text-xs); }
.bad { font-size: var(--text-xs); color: var(--danger); }
</style>
