<script setup lang="ts">
import { ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { Pencil } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'
import { toast } from '@/composables/toast'

const props = defineProps<{ chatId: string; roundId: string; summary: string | null; editable: boolean }>()
const qc = useQueryClient()
const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const error = ref<unknown>(null)

function start() {
  draft.value = props.summary ?? ''
  error.value = null
  editing.value = true
}
async function save() {
  saving.value = true
  error.value = null
  try {
    await api.putSummary(props.chatId, props.roundId, draft.value)
    editing.value = false
    toast('摘要已保存')
    for (const k of ['rounds', 'archive', 'memory']) qc.invalidateQueries({ queryKey: [k, props.chatId] })
  } catch (e) {
    error.value = e // keep the draft so edits are not lost
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="summary">
    <div class="row head">
      <span class="label">回合摘要</span>
      <span class="spacer" />
      <button v-if="editable && !editing" class="btn ghost small" type="button" @click="start"><Pencil /> 编辑</button>
    </div>
    <template v-if="editing">
      <textarea v-model="draft" class="textarea" rows="5" />
      <ErrorBox v-if="error" :error="error" title="保存失败" />
      <div class="row">
        <span class="spacer" />
        <button class="btn small" type="button" @click="editing = false">取消</button>
        <button class="btn primary small" type="button" :disabled="saving || !draft.trim()" @click="save">保存</button>
      </div>
    </template>
    <p v-else-if="summary" class="text">{{ summary }}</p>
    <p v-else class="faint text">尚未生成</p>
  </div>
</template>

<style scoped>
.summary { display: flex; flex-direction: column; gap: 6px; padding: 8px 12px; border-radius: var(--radius-m); background: var(--bg-sunken); font-size: 13px; }
.head { min-height: 28px; }
.text { white-space: pre-wrap; color: var(--text-muted); line-height: 1.65; }
</style>
