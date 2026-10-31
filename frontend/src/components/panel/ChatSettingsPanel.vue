<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { Save, Trash2 } from 'lucide-vue-next'
import { api, MODEL_PURPOSES, type ChatDetail, type ChatPatch, type ModelPurpose } from '@/api/endpoints'
import { PURPOSE_LABELS } from '@/lib/archive'
import ErrorBox from '../ErrorBox.vue'
import IllustrationSettingsSection from '@/features/illustrations/components/IllustrationSettingsSection.vue'
import RecallSettingsSection from '@/features/recall/components/RecallSettingsSection.vue'
import { toast } from '@/composables/toast'

const props = defineProps<{ chat: ChatDetail }>()
const qc = useQueryClient()
const router = useRouter()

const form = reactive({
  title: '', recent_rounds: 0, min_summaries: 0, writing_preset_id: '',
  bindings: {} as Record<ModelPurpose, string>,
})
function fill(c: ChatDetail) {
  form.title = c.title
  form.recent_rounds = c.recent_rounds
  form.min_summaries = c.min_summaries
  form.writing_preset_id = c.writing_preset_id ?? ''
  for (const p of MODEL_PURPOSES) form.bindings[p] = c.model_bindings[p] ?? ''
}
watch(() => props.chat, fill, { immediate: true })

const patch = computed<ChatPatch>(() => {
  const c = props.chat
  const body: ChatPatch = {}
  if (form.title !== c.title) body.title = form.title
  if (form.recent_rounds !== c.recent_rounds) body.recent_rounds = form.recent_rounds
  if (form.min_summaries !== c.min_summaries) body.min_summaries = form.min_summaries
  if ((form.writing_preset_id || null) !== c.writing_preset_id) body.writing_preset_id = form.writing_preset_id || null
  const bindings: Partial<Record<ModelPurpose, string>> = {}
  for (const p of MODEL_PURPOSES) if (form.bindings[p]) bindings[p] = form.bindings[p]
  if (JSON.stringify(bindings) !== JSON.stringify(Object.fromEntries(MODEL_PURPOSES.filter((p) => c.model_bindings[p]).map((p) => [p, c.model_bindings[p]])))) {
    body.model_bindings = bindings // replaces the whole mapping
  }
  return body
})
const dirty = computed(() => Object.keys(patch.value).length > 0)

const saving = ref(false)
const error = ref<unknown>(null)
async function save() {
  saving.value = true
  error.value = null
  try {
    const updated = await api.patchChat(props.chat.id, patch.value)
    qc.setQueryData(['chat', props.chat.id], updated)
    qc.invalidateQueries({ queryKey: ['chats'] })
    qc.invalidateQueries({ queryKey: ['memory', props.chat.id] })
    toast('设置已保存')
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}

const writingModel = computed(() => props.chat.model_configs.find((m) => m.id === form.bindings.writing))

async function removeChat() {
  if (!confirm(`删除聊天“${props.chat.title}”及其全部回合、状态和副本？此操作不可撤销。`)) return
  try {
    await api.deleteChat(props.chat.id)
    qc.invalidateQueries({ queryKey: ['chats'] })
    toast('聊天已删除')
    router.push('/')
  } catch (e) {
    error.value = e
  }
}
</script>

<template>
  <div class="stack">
    <div class="field"><label>标题</label><input v-model="form.title" class="input" /></div>
    <h3>记忆</h3>
    <div class="grid-2">
      <div class="field"><label>最近完整回合 X</label><input v-model.number="form.recent_rounds" class="input" type="number" min="0" /></div>
      <div class="field"><label>最少回合摘要 Y</label><input v-model.number="form.min_summaries" class="input" type="number" min="0" /></div>
    </div>
    <h3>写作预设</h3>
    <select v-model="form.writing_preset_id" class="select">
      <option value="">（未选择）</option>
      <option v-for="p in chat.writing_presets" :key="p.id" :value="p.id">{{ p.name }}</option>
    </select>
    <h3>模型绑定</h3>
    <div v-for="p in MODEL_PURPOSES" :key="p" class="field">
      <label>{{ PURPOSE_LABELS[p] }}</label>
      <select v-model="form.bindings[p]" class="select">
        <option value="">（未绑定）</option>
        <option v-for="m in chat.model_configs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
    <p v-if="writingModel" class="hint">写作模型 API 类型为 <code>{{ writingModel.api_type }}</code>，需与预设 build 返回的 <code>api_type</code> 一致。</p>
    <p class="hint">这里只能选择本聊天的副本。可以在“资源”标签中新增或编辑本聊天的预设与模型配置。</p>
    <ErrorBox v-if="error" :error="error" title="保存失败" />
    <div class="row">
      <button class="btn danger" type="button" @click="removeChat"><Trash2 /> 删除聊天</button>
      <span class="spacer" />
      <button class="btn" type="button" :disabled="!dirty" @click="fill(chat)">还原</button>
      <button class="btn primary" type="button" :disabled="!dirty || saving || !form.title.trim()" @click="save"><Save /> 保存</button>
    </div>
    <RecallSettingsSection :chat-id="chat.id" :model-configs="chat.model_configs" />
    <IllustrationSettingsSection :chat-id="chat.id" :model-configs="chat.model_configs" />
  </div>
</template>
