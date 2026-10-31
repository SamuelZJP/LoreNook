<script setup lang="ts">
import { reactive } from 'vue'
import type { ModelConfig } from '@/api/endpoints'
import { recallApi } from '../api'

/** Optional recall choices in the new-chat dialog; `apply` runs once the chat exists. */
defineProps<{ models: ModelConfig[] }>()
const form = reactive({ enabled: false, model_config_id: '', depth: 3, episode_limit: 2, summary_limit: 5 })

async function apply(chatId: string) {
  if (!form.enabled) return
  await recallApi.setup(chatId, { ...form, model_config_id: form.model_config_id || null })
}
defineExpose({ apply })
</script>

<template>
  <h3>记忆召回</h3>
  <label class="check"><input v-model="form.enabled" type="checkbox" /> 启用记忆召回</label>
  <div v-if="form.enabled" class="grid-2">
    <div class="field">
      <label>召回模型</label>
      <select v-model="form.model_config_id" class="select">
        <option value="">（未选择）</option>
        <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
    <div class="field">
      <label>回忆深度</label>
      <input v-model.number="form.depth" class="input" type="number" min="0" step="1" />
    </div>
    <div class="field">
      <label>情节上限</label>
      <input v-model.number="form.episode_limit" class="input" type="number" min="0" step="1" />
    </div>
    <div class="field">
      <label>摘要上限</label>
      <input v-model.number="form.summary_limit" class="input" type="number" min="0" step="1" />
    </div>
  </div>
</template>
