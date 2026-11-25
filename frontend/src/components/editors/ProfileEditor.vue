<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Download, Save, Trash2, FileCode } from 'lucide-vue-next'
import { api, definitionBase, type Character, type Identity, type SceneInput } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import AvatarUpload from '../AvatarUpload.vue'
import PortraitUpload from '../PortraitUpload.vue'
import PortraitEditor from '@/features/illustrations/components/PortraitEditor.vue'
import { illustrationsAvailable } from '@/features/illustrations/access'
import StatusBarEditor from '@/features/status_bar/components/StatusBarEditor.vue'
import ScopeNote from './ScopeNote.vue'
import InfoTip from '../InfoTip.vue'
import DefinitionsEditor from './DefinitionsEditor.vue'
import ScenesEditor, { newScene, worldState, type SceneDraft } from './ScenesEditor.vue'
import { isAdmin } from '@/features/account/session'
import { jsonProblem } from './JsonField.vue'
import { toast } from '@/composables/toast'
import schemaExample from '@examples/state/examples/basic.py?raw'
import scriptExample from '@examples/state/examples/script.py?raw'

/**
 * Character or user-identity editor. `chatId` selects the chat-owned copy;
 * `id === null` with no chat creates a new source record.
 */
const props = defineProps<{ kind: 'character' | 'identity'; id: string | null; chatId: string | null }>()
const emit = defineEmits<{ saved: [id: string]; deleted: [] }>()
const qc = useQueryClient()

type Profile = Character | Identity
const original = ref<Profile | null>(null)
const loading = ref(false)
const loadError = ref<unknown>(null)
const saveError = ref<unknown>(null)
const saving = ref(false)

const isCharacter = computed(() => props.kind === 'character')
const noun = computed(() => (isCharacter.value ? '角色' : '用户身份'))
const creating = computed(() => !props.chatId && !props.id)

const fields = ['name', 'avatar', 'portrait', 'description', 'state_schema', 'state_reference', 'state_update_rules', 'state_script'] as const
type Field = (typeof fields)[number]
const draft = reactive<Record<Field, string>>({
  name: '', avatar: '', portrait: '', description: '', state_schema: '', state_reference: '', state_update_rules: '', state_script: '',
})
// How many earlier states the state script receives; the one numeric profile field.
const scriptHistory = ref(0)
const scenes = ref<SceneDraft[]>([])
const activeFields = computed(() => (isCharacter.value ? fields : (['name', 'avatar', 'portrait', 'description'] as const)))

function fill(p: Profile | null, keepKeys = false) {
  for (const f of fields) {
    const v = p ? (p as unknown as Record<string, unknown>)[f] : undefined
    draft[f] = typeof v === 'string' ? v : ''
  }
  // Character Python runs on the server, so only administrators start from the example Schema.
  if (!p && isCharacter.value && isAdmin.value) draft.state_schema = schemaExample
  scriptHistory.value = p && 'state_script_history' in p ? p.state_script_history : 0
  const saved = p && 'scenes' in p ? p.scenes : []
  scenes.value = saved.length
    // Saving replaces scene rows, so keep the editor's keys to preserve expanded cards.
    ? saved.map((s, i) => ({ key: (keepKeys && scenes.value[i]?.key) || s.id, name: s.name, description: s.description, first_message: s.first_message,
      state: JSON.stringify(s.initial_state ?? {}, null, 2) }))
    : [newScene('默认', draft.state_schema.trim() ? '{}' : worldState())]
}

function sceneInputs(): SceneInput[] {
  return scenes.value.map((s, order) => ({ order, name: s.name, description: s.description,
    first_message: s.first_message, initial_state: JSON.parse(s.state) }))
}
const scenesInvalid = computed(() => isCharacter.value && scenes.value.some((s) => !s.name.trim() || jsonProblem(s.state)))
const scenesChanged = computed(() => {
  if (!isCharacter.value || scenesInvalid.value) return isCharacter.value
  const before = (original.value && 'scenes' in original.value ? original.value.scenes : [])
    .map(({ order, name, description, first_message, initial_state }) => ({ order, name, description, first_message, initial_state: initial_state ?? {} }))
  return JSON.stringify(sceneInputs()) !== JSON.stringify(before)
})

function fillSchemaExample() {
  if (!draft.state_schema.trim() || draft.state_schema === schemaExample || confirm('用示例覆盖当前 Schema？')) draft.state_schema = schemaExample
}
function fillScriptExample() {
  if (!draft.state_script.trim() || draft.state_script === scriptExample || confirm('用示例覆盖当前状态脚本？')) draft.state_script = scriptExample
}
const historyInvalid = computed(() => isCharacter.value && !(Number.isInteger(scriptHistory.value) && scriptHistory.value >= 0 && scriptHistory.value <= 100))
const historyChanged = computed(() => isCharacter.value && !historyInvalid.value
  && scriptHistory.value !== (original.value && 'state_script_history' in original.value ? original.value.state_script_history : 0))

async function load() {
  loadError.value = null
  saveError.value = null
  if (creating.value) {
    original.value = null
    fill(null)
    return
  }
  loading.value = true
  try {
    const p = props.chatId
      ? await (isCharacter.value ? api.chatCharacter(props.chatId) : api.chatIdentity(props.chatId))
      : await (isCharacter.value ? api.character(props.id!) : api.identity(props.id!))
    original.value = p
    fill(p)
  } catch (e) {
    loadError.value = e
  } finally {
    loading.value = false
  }
}
watch(() => [props.kind, props.id, props.chatId], load, { immediate: true })

// Image references are nullable: an empty draft means null.
const NULLABLE: readonly Field[] = ['avatar', 'portrait']
function value(f: Field): unknown {
  return (original.value as unknown as Record<string, unknown> | null)?.[f] ?? (NULLABLE.includes(f) ? null : '')
}
const outgoing = (f: Field) => (NULLABLE.includes(f) ? (draft[f].trim() || null) : draft[f])
const changed = computed(() => activeFields.value.filter((f) => outgoing(f) !== value(f)))

async function save() {
  saving.value = true
  saveError.value = null
  try {
    let saved: Profile
    if (creating.value) {
      const body: Record<string, unknown> = {}
      for (const f of activeFields.value) body[f] = outgoing(f)
      if (isCharacter.value) Object.assign(body, { scenes: sceneInputs(), state_script_history: scriptHistory.value })
      saved = isCharacter.value ? await api.createCharacter(body as never) : await api.createIdentity(body as never)
    } else {
      // PATCH only what changed.
      const body: Record<string, unknown> = {}
      for (const f of changed.value) body[f] = outgoing(f)
      if (scenesChanged.value) body.scenes = sceneInputs()
      if (historyChanged.value) body.state_script_history = scriptHistory.value
      if (props.chatId) {
        saved = isCharacter.value ? await api.patchChatCharacter(props.chatId, body) : await api.patchChatIdentity(props.chatId, body)
      } else {
        saved = isCharacter.value ? await api.patchCharacter(props.id!, body) : await api.patchIdentity(props.id!, body)
      }
    }
    original.value = saved
    fill(saved, true)
    qc.invalidateQueries({ queryKey: [isCharacter.value ? 'characters' : 'identities'] })
    if (props.chatId) qc.invalidateQueries({ queryKey: ['chat', props.chatId] })
    toast(creating.value ? `${noun.value}已创建` : '已保存')
    emit('saved', saved.id)
  } catch (e) {
    saveError.value = e // draft stays intact
  } finally {
    saving.value = false
  }
}

const exporting = ref(false)
async function exportCard() {
  exporting.value = true
  try {
    await api.exportCard(props.chatId ? { chatId: props.chatId } : { characterId: props.id! })
  } catch (error) {
    toast(error instanceof Error ? error.message : String(error), 'error')
  } finally {
    exporting.value = false
  }
}

async function remove() {
  if (!props.id || props.chatId) return
  if (!confirm(`删除这个${noun.value}？已创建的聊天中的副本不受影响。`)) return
  try {
    await (isCharacter.value ? api.deleteCharacter(props.id) : api.deleteIdentity(props.id))
    qc.invalidateQueries({ queryKey: [isCharacter.value ? 'characters' : 'identities'] })
    toast('已删除')
    emit('deleted')
  } catch (e) {
    saveError.value = e
  }
}

type Tab = 'basic' | 'scenes' | 'state' | 'definitions' | 'portrait' | 'status-bar'
const tab = ref<Tab>('basic')
interface TabInfo { id: Tab; label: string; fields: Field[]; advanced?: boolean }
const tabs = computed<TabInfo[]>(() => [
  { id: 'basic', label: '基本信息', fields: ['name', 'avatar', 'portrait', 'description'] },
  ...(isCharacter.value ? [{ id: 'scenes' as const, label: '开场', fields: [] }] : []),
  // Advanced: what shapes the AI's reading of the profile. Definitions, portrait and status bar
  // save on their own against an existing record, so they appear once it exists.
  ...(creating.value ? [] : [
    { id: 'definitions' as const, label: '设定', fields: [], advanced: true },
    { id: 'portrait' as const, label: '插图外貌', fields: [], advanced: true },
    ...(isCharacter.value ? [{ id: 'status-bar' as const, label: '状态栏', fields: [], advanced: true }] : []),
  ]),
  ...(isCharacter.value ? [{ id: 'state' as const, label: '状态规则', fields: ['state_schema', 'state_reference', 'state_update_rules', 'state_script'] as Field[], advanced: true }] : []),
])
const firstAdvanced = computed(() => tabs.value.find((t) => t.advanced)?.id)
// These tabs save on their own, so the profile's save row doesn't apply to them.
const ownSave = computed(() => tab.value === 'definitions' || tab.value === 'portrait' || tab.value === 'status-bar')
watch(() => props.kind, () => { if (!tabs.value.some((t) => t.id === tab.value)) tab.value = 'basic' })
const tabDirty = (id: Tab, fs: Field[]) =>
  !creating.value && (fs.some((f) => changed.value.includes(f)) || (id === 'scenes' && scenesChanged.value) || (id === 'state' && historyChanged.value))
const unsaved = computed(() => changed.value.length + (scenesChanged.value ? 1 : 0) + (historyChanged.value ? 1 : 0))

const defBase = computed(() => (original.value ? definitionBase(props.kind, original.value.id, props.chatId) : null))
</script>

<template>
  <div class="stack">
    <ScopeNote :chat-id="chatId" :what="noun" />
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <div v-if="loading" class="empty">加载中…</div>
    <template v-else-if="!loadError">
      <nav class="tabs">
        <template v-for="t in tabs" :key="t.id">
          <span v-if="t.id === firstAdvanced" class="tab-group" aria-hidden="true">进阶</span>
          <button type="button" :class="{ active: tab === t.id, advanced: t.advanced }" @click="tab = t.id">
            {{ t.label }}<span v-if="tabDirty(t.id, t.fields)" class="dot" title="有未保存的修改" />
          </button>
        </template>
      </nav>

      <section v-show="tab === 'basic'" class="basic">
        <PortraitUpload v-model="draft.portrait" class="portrait">
          <template #badge><AvatarUpload v-model="draft.avatar" :name="draft.name" /></template>
        </PortraitUpload>
        <div class="identity">
          <input v-model="draft.name" class="name-input" :placeholder="isCharacter ? '角色名' : '你的名字'" aria-label="名称" />
          <textarea
            v-model="draft.description" class="desc-input" rows="3" aria-label="简介"
            :placeholder="isCharacter ? '一句话介绍这个角色' : '一句话介绍你在故事里的样子'"
          />
        </div>
      </section>

      <section v-if="isCharacter" v-show="tab === 'scenes'" class="stack">
        <ScenesEditor v-model="scenes" :state-schema="draft.state_schema" :chat-scoped="!!chatId" />
      </section>

      <section v-if="isCharacter" v-show="tab === 'state'" class="stack">
        <p v-if="!isAdmin" class="hint">
          状态 Schema 和状态脚本是在服务器上运行的 Python 代码，只有管理员可以编写。没有 Schema 时，开场的初始变量需要写全「世界」的日期、星期、时间和地点。
        </p>
        <div v-if="isAdmin" class="field">
          <div class="row">
            <label class="label">状态 Schema（Python / Pydantic）</label>
            <InfoTip>
              导出名为 <code>Schema</code> 的模型，必须包含 <code>世界</code> 对象：<code>日期</code>（YYYY-MM-DD）、<code>星期</code>、<code>时间</code>（HH:mm）、<code>地点</code>。
              默认值与开场的初始变量合并成初始状态。
            </InfoTip>
            <span class="grow" />
            <button class="btn small" type="button" @click="fillSchemaExample"><FileCode /> 填入示例</button>
          </div>
          <CodeEditor v-model="draft.state_schema" language="python" min-height="220px" />
        </div>
        <div class="field"><label>状态参考信息</label><textarea v-model="draft.state_reference" class="textarea" rows="4" /></div>
        <div class="field"><label>状态更新规则</label><textarea v-model="draft.state_update_rules" class="textarea" rows="4" /></div>
        <div v-if="isAdmin" class="field">
          <div class="row">
            <label class="label">状态脚本（Python，可留空）</label>
            <InfoTip>
              定义 <code>process(state, previous, history)</code>，返回要保存的状态；抛出异常则本次更新失败。
              <code>history</code> 是更早的状态列表，旧的在前，以 <code>previous</code> 结尾。
            </InfoTip>
            <span class="grow" />
            <button class="btn small" type="button" @click="fillScriptExample"><FileCode /> 填入示例</button>
          </div>
          <CodeEditor v-model="draft.state_script" language="python" min-height="160px" />
        </div>
        <div v-if="isAdmin" class="field">
          <div class="row tight-row"><label class="label">脚本可见的历史状态数</label><InfoTip>0–100。0 表示 <code>history</code> 为空。</InfoTip></div>
          <input v-model.number="scriptHistory" class="input history" type="number" min="0" max="100" step="1" />
        </div>
      </section>

      <ErrorBox v-if="saveError && !ownSave" :error="saveError" title="保存失败" />
      <div v-show="!ownSave" class="row actions">
        <button v-if="id && !chatId" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <button
          v-if="isCharacter && !creating" class="btn" type="button" :disabled="exporting"
          :title="unsaved ? '导出的是已保存的内容' : undefined" @click="exportCard"
        ><Download /> 导出角色卡</button>
        <span class="spacer" />
        <span v-if="scenesInvalid" class="hint bad">开场需要名称和有效的 JSON 初始变量</span>
        <span v-else-if="historyInvalid" class="hint bad">历史状态数量需为 0–100 的整数</span>
        <span v-else-if="!creating && unsaved" class="hint">{{ unsaved }} 项未保存</span>
        <button class="btn primary" type="button" :disabled="saving || !draft.name.trim() || scenesInvalid || historyInvalid || (!creating && !unsaved)" @click="save">
          <Save /> {{ creating ? '创建' : '保存' }}
        </button>
      </div>

      <section v-if="tab === 'definitions'" class="stack">
        <DefinitionsEditor v-if="defBase" :base="defBase" :chat-id="chatId" :title="`${noun}设定`" />
      </section>

      <section v-if="tab === 'portrait'" class="stack">
        <PortraitEditor v-if="original && illustrationsAvailable" :kind="kind" :owner-id="original.id" :chat-id="chatId" />
      </section>

      <section v-if="tab === 'status-bar'" class="stack">
        <StatusBarEditor v-if="original && 'scenes' in original" :character="original" :chat-id="chatId" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.tab-group {
  align-self: center; margin-left: var(--space-3); padding-left: var(--space-3); border-left: 1px solid var(--border);
  font-size: var(--text-xs); color: var(--text-faint); letter-spacing: 0.08em; white-space: nowrap;
}
.tabs button.advanced { font-weight: 400; }
.dot { display: inline-block; width: 6px; height: 6px; margin-left: var(--space-1); border-radius: 50%; background: var(--warn); vertical-align: middle; }
.bad { color: var(--danger); }
/* Portrait on the left, name and introduction beside it; they stack when the pane is narrow. */
.basic { display: flex; flex-wrap: wrap; gap: var(--space-6); align-items: flex-start; padding-top: var(--space-2); }
.portrait { width: 200px; flex-shrink: 0; }
.identity { flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: var(--space-3); }
.name-input, .desc-input {
  width: 100%; border: 0; background: none; color: var(--text); padding: var(--space-1) 0; outline: none;
}
.name-input {
  font-family: var(--font-reading); font-size: var(--text-3xl); font-weight: 600; letter-spacing: 0.02em;
  border-bottom: 1px solid var(--border); transition: border-color 0.15s;
}
.name-input:focus { border-bottom-color: var(--accent); }
.desc-input {
  font-family: var(--font-reading); font-size: var(--text-lg); line-height: 1.8; color: var(--text-muted);
  resize: none; field-sizing: content; min-height: calc(3 * 1.8em);
}
.name-input::placeholder, .desc-input::placeholder { color: var(--text-faint); }
.tight-row { gap: var(--space-1); }
.history { max-width: 160px; }
.actions { position: sticky; bottom: 0; background: var(--bg-elev); padding: var(--space-2) 0; z-index: 1; }
</style>
