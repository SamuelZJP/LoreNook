<script setup lang="ts">
import { reactive } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { ModelConfig } from '@/api/endpoints'
import { illustrationApi, type IllustrationMode } from '../api'
import { MODE_LABELS } from '../lib'

/** Optional illustration choices in the new-chat dialog; `apply` runs once the chat exists. */
defineProps<{ models: ModelConfig[] }>()
const workflows = useQuery({ queryKey: ['workflows', null], queryFn: () => illustrationApi.workflows({ chatId: null }) })
const form = reactive({ mode: 'off' as IllustrationMode, image_workflow_id: '', model_config_id: '' })

async function apply(chatId: string) {
  if (form.mode === 'off') return
  await illustrationApi.setup(chatId, {
    mode: form.mode, image_workflow_id: form.image_workflow_id || null, model_config_id: form.model_config_id || null,
  })
}
defineExpose({ apply })
</script>

<template>
  <h3>插图</h3>
  <div class="field">
    <label>生成时机</label>
    <select v-model="form.mode" class="select">
      <option v-for="(label, mode) in MODE_LABELS" :key="mode" :value="mode">{{ label }}</option>
    </select>
  </div>
  <div v-if="form.mode !== 'off'" class="grid-2">
    <div class="field">
      <label>图像工作流</label>
      <select v-model="form.image_workflow_id" class="select">
        <option value="">（未选择）</option>
        <option v-for="w in workflows.data.value" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
    </div>
    <div class="field">
      <label>提示词模型</label>
      <select v-model="form.model_config_id" class="select">
        <option value="">（未选择）</option>
        <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
  </div>
  <p v-if="form.mode !== 'off' && !workflows.data.value?.length" class="hint">资源库中还没有图像工作流，可以先在资源库创建，或稍后在聊天资源中添加。</p>
</template>
