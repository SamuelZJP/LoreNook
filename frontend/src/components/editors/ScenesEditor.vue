<script setup lang="ts">
import { ref } from 'vue'
import { ArrowUp, ArrowDown, Plus, Trash2, ChevronRight, Eye } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'
import InfoTip from '../InfoTip.vue'
import JsonField, { jsonProblem } from './JsonField.vue'

/** Opening scenes of one character. The parent owns the drafts and saves them with the character. */
export interface SceneDraft { key: string; name: string; description: string; first_message: string; state: string }

const props = defineProps<{ stateSchema: string; chatScoped: boolean }>()
const scenes = defineModel<SceneDraft[]>({ required: true })

// A lone scene is always expanded; with several, cards start collapsed.
const open = ref(new Set<string>())
const isOpen = (key: string) => scenes.value.length === 1 || open.value.has(key)
function toggle(key: string) {
  const next = new Set(open.value)
  next.has(key) ? next.delete(key) : next.add(key)
  open.value = next
}

function add() {
  const scene = newScene(`开场 ${scenes.value.length + 1}`)
  scenes.value = [...scenes.value, scene]
  open.value = new Set([...open.value, scene.key])
}
function remove(index: number) {
  if (!confirm(`删除开场「${scenes.value[index].name}」？保存角色后生效。`)) return
  scenes.value = scenes.value.filter((_, i) => i !== index)
}
function move(index: number, delta: number) {
  const next = [...scenes.value]
  ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
  scenes.value = next
}

const previews = ref<Record<string, string>>({})
const previewErrors = ref<Record<string, unknown>>({})
async function preview(scene: SceneDraft) {
  delete previewErrors.value[scene.key]
  delete previews.value[scene.key]
  try {
    const state = await api.previewInitialState({ state_schema: props.stateSchema, initial_state: JSON.parse(scene.state) })
    previews.value[scene.key] = JSON.stringify(state, null, 2)
  } catch (e) {
    previewErrors.value[scene.key] = e
  }
}
</script>

<script lang="ts">
let counter = 0
export function newScene(name = '默认'): SceneDraft {
  return { key: `new-${++counter}`, name, description: '', first_message: '', state: '{}' }
}
</script>

<template>
  <div class="stack">
    <div class="row wrap">
      <h3>开场</h3>
      <InfoTip v-if="!chatScoped">
        每个开场是一段开场白加一组初始变量，新建聊天时选一个。初始变量只需写与默认值不同的部分，例如 <code>{"世界": {"地点": "教室"}}</code>。
      </InfoTip>
      <span class="grow" />
      <button v-if="!chatScoped" class="btn small" type="button" @click="add"><Plus /> 新增</button>
    </div>

    <div v-for="(s, i) in scenes" :key="s.key" class="scene card" :class="{ open: isOpen(s.key) }">
      <div class="head">
        <button class="toggle" type="button" :aria-expanded="isOpen(s.key)" @click="toggle(s.key)">
          <ChevronRight class="chevron" />
          <span class="badge">#{{ i + 1 }}</span>
          <span class="name">{{ s.name || '（未命名）' }}</span>
          <span class="preview">{{ s.description }}</span>
          <span v-if="jsonProblem(s.state)" class="badge danger">JSON 无效</span>
        </button>
        <template v-if="!chatScoped">
          <button class="btn ghost icon small" type="button" title="上移" :disabled="i === 0" @click="move(i, -1)"><ArrowUp /></button>
          <button class="btn ghost icon small" type="button" title="下移" :disabled="i === scenes.length - 1" @click="move(i, 1)"><ArrowDown /></button>
          <button class="btn ghost icon small danger" type="button" title="删除" :disabled="scenes.length === 1" @click="remove(i)"><Trash2 /></button>
        </template>
      </div>
      <div v-if="isOpen(s.key)" class="body">
        <div class="grid-2">
          <div class="field"><label>名称</label><input v-model="s.name" class="input" /></div>
          <div class="field"><label>说明</label><input v-model="s.description" class="input" placeholder="新建聊天时显示" /></div>
        </div>
        <div class="field">
          <label>开场消息（第 0 楼）</label>
          <textarea v-model="s.first_message" class="textarea" rows="6" />
        </div>
        <JsonField v-model="s.state" label="初始变量" min-height="80px" />
        <div class="row">
          <span class="spacer" />
          <button class="btn small" type="button" :disabled="!!jsonProblem(s.state)" @click="preview(s)"><Eye /> 预览初始状态</button>
        </div>
        <ErrorBox v-if="previewErrors[s.key]" :error="previewErrors[s.key]" title="初始状态无效" />
        <JsonField v-if="previews[s.key]" :model-value="previews[s.key]" label="完整初始状态（按当前 Schema 草稿计算）" readonly min-height="80px" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.scene { padding: var(--space-1) var(--space-1-5); display: flex; flex-direction: column; gap: var(--space-2); }
.scene.open { padding-bottom: var(--space-3); }
.head { display: flex; align-items: center; gap: var(--space-0-5); }
.toggle {
  display: flex; align-items: center; gap: var(--space-1-5); flex: 1; min-width: 0; height: 32px; padding: 0 var(--space-1);
  border: 0; border-radius: var(--radius-s); background: none; color: inherit; font: inherit; font-size: var(--text-sm); text-align: left; cursor: pointer;
}
.toggle:hover { background: var(--bg-hover); }
.toggle .badge, .name { flex: none; }
.chevron { width: 14px; height: 14px; flex: none; color: var(--text-muted); transition: transform 0.15s; }
.open .chevron { transform: rotate(90deg); }
.preview { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); }
.body { display: flex; flex-direction: column; gap: var(--space-2); padding: 0 var(--space-1); }
</style>
