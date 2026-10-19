<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Save, Trash2, FileCode } from 'lucide-vue-next'
import { api, definitionBase, type Character, type Identity } from '@/api/endpoints'
import CodeEditor from '../CodeEditor.vue'
import ErrorBox from '../ErrorBox.vue'
import AvatarBadge from '../AvatarBadge.vue'
import ScopeNote from './ScopeNote.vue'
import DefinitionsEditor from './DefinitionsEditor.vue'
import { toast } from '@/composables/toast'
import schemaExample from '@examples/state/examples/basic.py?raw'

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

const fields = ['name', 'avatar', 'description', 'first_message', 'state_schema', 'state_reference', 'state_update_rules'] as const
type Field = (typeof fields)[number]
const draft = reactive<Record<Field, string>>({
  name: '', avatar: '', description: '', first_message: '', state_schema: '', state_reference: '', state_update_rules: '',
})
const activeFields = computed(() => (isCharacter.value ? fields : (['name', 'avatar', 'description'] as const)))

function fill(p: Profile | null) {
  for (const f of fields) {
    const v = p ? (p as unknown as Record<string, unknown>)[f] : undefined
    draft[f] = typeof v === 'string' ? v : ''
  }
  if (!p && isCharacter.value) draft.state_schema = schemaExample
}

function fillSchemaExample() {
  if (!draft.state_schema.trim() || draft.state_schema === schemaExample || confirm('用示例覆盖当前 Schema？')) draft.state_schema = schemaExample
}

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
      saved = isCharacter.value ? await api.createCharacter(body as never) : await api.createIdentity(body as never)
    } else {
      // PATCH only what changed; avatar is the one nullable field.
      const body: Record<string, unknown> = {}
      for (const f of changed.value) body[f] = f === 'avatar' ? (draft.avatar.trim() || null) : draft[f]
      if (props.chatId) {
        saved = isCharacter.value ? await api.patchChatCharacter(props.chatId, body) : await api.patchChatIdentity(props.chatId, body)
      } else {
        saved = isCharacter.value ? await api.patchCharacter(props.id!, body) : await api.patchIdentity(props.id!, body)
      }
    }
    original.value = saved
    fill(saved)
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

const defBase = computed(() => (original.value ? definitionBase(props.kind, original.value.id, props.chatId) : null))
</script>

<template>
  <div class="stack">
    <ScopeNote :chat-id="chatId" :what="noun" />
    <ErrorBox v-if="loadError" :error="loadError" title="读取失败" />
    <div v-if="loading" class="empty">加载中…</div>
    <template v-else-if="!loadError">
      <div class="row">
        <AvatarBadge :name="draft.name" :src="draft.avatar" :size="52" />
        <div class="grow stack tight">
          <div class="field"><label>名称</label><input v-model="draft.name" class="input" /></div>
        </div>
      </div>
      <div class="field">
        <label>头像引用</label>
        <input v-model="draft.avatar" class="input" placeholder="图片 URL 或路径（可留空）" />
        <span class="hint">后端只保存引用文本，没有上传功能。</span>
      </div>
      <div class="field"><label>描述</label><textarea v-model="draft.description" class="textarea" rows="3" /></div>

      <template v-if="isCharacter">
        <div class="field">
          <label>开场消息（第 0 楼）</label>
          <textarea v-model="draft.first_message" class="textarea" rows="6" />
        </div>
        <div class="field">
          <div class="row">
            <label class="label grow">状态 Schema（Python / Pydantic）</label>
            <button class="btn small" type="button" @click="fillSchemaExample"><FileCode /> 填入示例</button>
          </div>
          <CodeEditor v-model="draft.state_schema" language="python" min-height="220px" />
          <span class="hint">
            源码需导出名为 <code>Schema</code> 的模型，其默认值生成初始状态，并且必须包含 <code>世界</code> 对象：
            <code>日期</code>（YYYY-MM-DD）、<code>星期</code>（星期一–星期日）、<code>时间</code>（HH:mm）、<code>地点</code>。
            创建或修改 Schema 时后端会校验默认初始状态，空 Schema 无效。
          </span>
        </div>
        <div class="field"><label>状态参考信息</label><textarea v-model="draft.state_reference" class="textarea" rows="4" /></div>
        <div class="field"><label>状态更新规则</label><textarea v-model="draft.state_update_rules" class="textarea" rows="4" /></div>
      </template>

      <ErrorBox v-if="saveError" :error="saveError" title="保存失败" />
      <div class="row actions">
        <button v-if="id && !chatId" class="btn danger" type="button" @click="remove"><Trash2 /> 删除</button>
        <span class="spacer" />
        <span v-if="!creating && changed.length" class="hint">{{ changed.length }} 项未保存</span>
        <button class="btn primary" type="button" :disabled="saving || !draft.name.trim() || (!creating && !changed.length)" @click="save">
          <Save /> {{ creating ? '创建' : '保存' }}
        </button>
      </div>

      <DefinitionsEditor v-if="defBase" :base="defBase" :chat-id="chatId" :title="`${noun}定义`" />
      <p v-else-if="creating" class="hint">创建后可以添加定义条目。</p>
    </template>
  </div>
</template>

<style scoped>
.actions { position: sticky; bottom: 0; background: var(--bg-elev); padding: 8px 0; z-index: 1; }
</style>
