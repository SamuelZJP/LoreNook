<script setup lang="ts">
import { reactive } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { illustrationApi, type IllustrationMode } from '../api'
import { MODE_LABELS } from '../lib'

/**
 * Optional illustration choices in the new-chat form. `snapshot`/`restore` carry them in a chat
 * template; `apply` runs once the chat exists.
 */
const workflows = useQuery({ queryKey: ['workflows', null], queryFn: () => illustrationApi.workflows({ chatId: null }) })
const form = reactive({ mode: 'off' as IllustrationMode, image_workflow_id: '' })

function restore(entry: Record<string, unknown> | undefined) {
  const e = entry ?? {}
  form.mode = typeof e.mode === 'string' && e.mode in MODE_LABELS ? (e.mode as IllustrationMode) : 'off'
  form.image_workflow_id = typeof e.image_workflow_id === 'string' ? e.image_workflow_id : ''
}

function snapshot(): Record<string, unknown> {
  return { ...form }
}

async function apply(chatId: string) {
  if (form.mode === 'off') return
  // A template may name a workflow deleted since; leave it unselected rather than fail.
  const list = workflows.data.value
  const id = form.image_workflow_id && (!list || list.some((w) => w.id === form.image_workflow_id)) ? form.image_workflow_id : null
  await illustrationApi.setup(chatId, { mode: form.mode, image_workflow_id: id })
}
defineExpose({ apply, snapshot, restore })
</script>

<template>
  <h3>插图</h3>
  <div class="field">
    <label>生成时机</label>
    <select v-model="form.mode" class="select">
      <option v-for="(label, mode) in MODE_LABELS" :key="mode" :value="mode">{{ label }}</option>
    </select>
  </div>
  <div v-if="form.mode !== 'off'" class="field">
    <label>图像工作流</label>
    <select v-model="form.image_workflow_id" class="select">
      <option value="">（未选择）</option>
      <option v-for="w in workflows.data.value" :key="w.id" :value="w.id">{{ w.name }}</option>
    </select>
  </div>
  <p v-if="form.mode !== 'off' && !workflows.data.value?.length" class="hint">资源库中还没有图像工作流，可以先在资源库创建，或稍后在聊天资源中添加。</p>
</template>
