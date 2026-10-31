<script setup lang="ts">
import { reactive } from 'vue'
import type { ModelConfig } from '@/api/endpoints'
import { recallApi } from '../api'

/** Optional recall choices in the new-chat dialog; `apply` runs once the chat exists. */
defineProps<{ models: ModelConfig[] }>()
const form = reactive({ model_config_id: '', depth: 3 })

async function apply(chatId: string) {
  if (!form.model_config_id) return
  await recallApi.setup(chatId, { model_config_id: form.model_config_id, depth: form.depth })
}
defineExpose({ apply })
</script>

<template>
  <h3>记忆召回</h3>
  <div class="grid-2">
    <div class="field">
      <label>召回模型</label>
      <select v-model="form.model_config_id" class="select">
        <option value="">（关闭召回）</option>
        <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
    <div v-if="form.model_config_id" class="field">
      <label>回忆深度</label>
      <input v-model.number="form.depth" class="input" type="number" min="0" step="1" />
    </div>
  </div>
</template>
