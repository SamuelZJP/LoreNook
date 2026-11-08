<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2, FileCode } from 'lucide-vue-next'
import { api, definitionBase, type Character, type Identity, type SceneInput } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import AvatarBadge from '../AvatarBadge.vue'
import ImageUpload from '../ImageUpload.vue'
import PortraitEditor from '@/features/illustrations/components/PortraitEditor.vue'
import StatusBarEditor from '@/features/status_bar/components/StatusBarEditor.vue'
import ScopeNote from './ScopeNote.vue'
import DefinitionsEditor from './DefinitionsEditor.vue'
import ScenesEditor, { newScene, type SceneDraft } from './ScenesEditor.vue'
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

const fields = ['name', 'avatar', 'description', 'state_schema', 'state_reference', 'state_update_rules', 'state_script'] as const
type Field = (typeof fields)[number]
const draft = reactive<Record<Field, string>>({
  name: '', avatar: '', description: '', state_schema: '', state_reference: '', state_update_rules: '', state_script: '',
})
// How many earlier states the state script receives; the one numeric profile field.
const scriptHistory = ref(0)
const scenes = ref<SceneDraft[]>([])
const activeFields = computed(() => (isCharacter.value ? fields : (['name', 'avatar', 'description'] as const)))

function fill(p: Profile | null, keepKeys = false) {
  for (const f of fields) {
    const v = p ? (p as unknown as Record<string, unknown>)[f] : undefined
    draft[f] = typeof v === 'string' ? v : ''
  }
  if (!p && isCharacter.value) draft.state_schema = schemaExample
  scriptHistory.value = p && 'state_script_history' in p ? p.state_script_history : 0
  const saved = p && 'scenes' in p ? p.scenes : []
  scenes.value = saved.length
    // Saving replaces scene rows, so keep the editor's keys to preserve expanded cards.
    ? saved.map((s, i) => ({ key: (keepKeys && scenes.value[i]?.key) || s.id, name: s.name, description: s.description, first_message: s.first_message,
      state: JSON.stringify(s.initial_state ?? {}, null, 2) }))
    : [newScene()]
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

function value(f: Field): unknown {
  return (original.value as unknown as Record<string, unknown> | null)?.[f] ?? (f === 'avatar' ? null : '')
}
const changed = computed(() => activeFields.value.filter((f) => {
  const now = f === 'avatar' ? (draft.avatar.trim() || null) : draft[f]
  return now !== value(f)
}))

async function save() {
  saving.value = true
  saveError.value = null
  try {
    let saved: Profile
    if (creating.value) {
      const body: Record<string, unknown> = {}
      for (const f of activeFields.value) body[f] = f === 'avatar' ? (draft.avatar.trim() || null) : draft[f]
      if (isCharacter.value) Object.assign(body, { scenes: sceneInputs(), state_script_history: scriptHistory.value })
      saved = isCharacter.value ? await api.createCharacter(body as never) : await api.createIdentity(body as never)
    } else {
      // PATCH only what changed; avatar is the one nullable field.
      const body: Record<string, unknown> = {}
      for (const f of changed.value) body[f] = f === 'avatar' ? (draft.avatar.trim() || null) : draft[f]
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
const tabs = computed(() => [
  { id: 'basic' as const, label: '基本信息', fields: ['name', 'avatar', 'description'] as Field[] },
  ...(isCharacter.value ? [{ id: 'scenes' as const, label: '开场', fields: [] as Field[] }] : []),
  ...(isCharacter.value ? [{ id: 'state' as const, label: '状态', fields: ['state_schema', 'state_reference', 'state_update_rules', 'state_script'] as Field[] }] : []),
  { id: 'definitions' as const, label: `${noun.value}定义`, fields: [] as Field[] },
  { id: 'portrait' as const, label: '画像', fields: [] as Field[] },
  ...(isCharacter.value ? [{ id: 'status-bar' as const, label: '状态栏', fields: [] as Field[] }] : []),
])
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
        <button v-for="t in tabs" :key="t.id" type="button" :class="{ active: tab === t.id }" @click="tab = t.id">
          {{ t.label }}<span v-if="tabDirty(t.id, t.fields)" class="dot" title="有未保存的修改" />
        </button>
      </nav>

      <section v-show="tab === 'basic'" class="stack">
        <div class="row">
          <AvatarBadge :name="draft.name" :src="draft.avatar" :size="52" />
          <div class="grow stack tight">
            <div class="field"><label>名称</label><input v-model="draft.name" class="input" /></div>
          </div>
        </div>
        <div class="field">
          <label>头像</label>
          <div class="row avatar-row">
            <ImageUpload :model-value="draft.avatar || null" label="上传头像" value="url" :size="72" @update:model-value="draft.avatar = $event ?? ''" />
            <input v-model="draft.avatar" class="input grow" placeholder="或填写图片 URL（可留空）" aria-label="头像 URL" />
          </div>
        </div>
        <div class="field"><label>描述</label><textarea v-model="draft.description" class="textarea" rows="3" /></div>
      </section>

      <section v-if="isCharacter" v-show="tab === 'scenes'" class="stack">
        <ScenesEditor v-model="scenes" :state-schema="draft.state_schema" :chat-scoped="!!chatId" />
      </section>

      <section v-if="isCharacter" v-show="tab === 'state'" class="stack">
        <div class="field">
          <div class="row">
            <label class="label grow">状态 Schema（Python / Pydantic）</label>
            <button class="btn small" type="button" @click="fillSchemaExample"><FileCode /> 填入示例</button>
          </div>
          <CodeEditor v-model="draft.state_schema" language="python" min-height="220px" />
          <span class="hint">
            源码需导出名为 <code>Schema</code> 的模型，其默认值与各开场的初始变量合并生成初始状态，并且必须包含 <code>世界</code> 对象：
            <code>日期</code>（YYYY-MM-DD）、<code>星期</code>（星期一–星期日）、<code>时间</code>（HH:mm）、<code>地点</code>。
            创建或修改 Schema 时后端会校验每个开场的初始状态。
          </span>
        </div>
        <div class="field"><label>状态参考信息</label><textarea v-model="draft.state_reference" class="textarea" rows="4" /></div>
        <div class="field"><label>状态更新规则</label><textarea v-model="draft.state_update_rules" class="textarea" rows="4" /></div>
        <div class="field">
          <div class="row">
            <label class="label grow">状态脚本（Python，可留空）</label>
            <button class="btn small" type="button" @click="fillScriptExample"><FileCode /> 填入示例</button>
          </div>
          <CodeEditor v-model="draft.state_script" language="python" min-height="160px" />
          <span class="hint">
            每次状态更新在模型的变更通过 Schema 校验后运行：<code>process(state, previous, history)</code> 返回要保存的状态，抛出异常则本次状态更新失败。
            <code>previous</code> 是本回合之前的状态，<code>history</code> 是最近若干个之前的状态（旧→新，以 <code>previous</code> 结尾，<code>[{round_no, state}]</code>，初始状态的 round_no 为 0）。
            返回结果会再次经过 Schema 校验。
          </span>
        </div>
        <div class="field">
          <label>历史状态数量</label>
          <input v-model.number="scriptHistory" class="input" type="number" min="0" max="100" step="1" />
          <span class="hint"><code>history</code> 包含的状态数，0–100，0 表示空列表。</span>
        </div>
      </section>

      <ErrorBox v-if="saveError && !ownSave" :error="saveError" title="保存失败" />
      <div v-show="!ownSave" class="row actions">
        <button v-if="id && !chatId" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <span v-if="scenesInvalid" class="hint bad">开场需要名称和有效的 JSON 初始变量</span>
        <span v-else-if="historyInvalid" class="hint bad">历史状态数量需为 0–100 的整数</span>
        <span v-else-if="!creating && unsaved" class="hint">{{ unsaved }} 项未保存</span>
        <button class="btn primary" type="button" :disabled="saving || !draft.name.trim() || scenesInvalid || historyInvalid || (!creating && !unsaved)" @click="save">
          <Save /> {{ creating ? '创建' : '保存' }}
        </button>
      </div>

      <section v-if="tab === 'definitions'" class="stack">
        <DefinitionsEditor v-if="defBase" :base="defBase" :chat-id="chatId" :title="`${noun}定义`" />
        <template v-else-if="creating">
          <h3>{{ noun }}定义</h3>
          <p class="hint">创建后可以添加定义条目。</p>
        </template>
      </section>

      <section v-if="tab === 'portrait'" class="stack">
        <PortraitEditor v-if="original" :kind="kind" :owner-id="original.id" :chat-id="chatId" />
        <p v-else class="hint">创建后可以设置画像。</p>
      </section>

      <section v-if="tab === 'status-bar'" class="stack">
        <StatusBarEditor v-if="original && 'scenes' in original" :character="original" :chat-id="chatId" />
        <p v-else class="hint">创建后可以编写状态栏。</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.dot { display: inline-block; width: 6px; height: 6px; margin-left: 5px; border-radius: 50%; background: var(--warn); vertical-align: middle; }
.bad { color: var(--danger); }
.avatar-row { align-items: flex-start; }
.actions { position: sticky; bottom: 0; background: var(--bg-elev); padding: 8px 0; z-index: 1; }
</style>
