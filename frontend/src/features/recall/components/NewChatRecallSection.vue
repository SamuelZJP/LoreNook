<script setup lang="ts">
import { reactive } from 'vue'
import type { ModelConfig } from '@/api/endpoints'
import { recallApi } from '../api'

/**
 * Optional recall choices in the new-chat form. `snapshot`/`restore` carry them in a chat template;
 * `apply` runs once the chat exists.
 */
const props = defineProps<{ models: ModelConfig[] }>()
const DEFAULTS = { enabled: false, model_config_id: '', depth: 3, episode_limit: 2, summary_limit: 5 }
const form = reactive({ ...DEFAULTS })

const count = (value: unknown, fallback: number) => (Number.isInteger(value) && (value as number) >= 0 ? (value as number) : fallback)

function restore(entry: Record<string, unknown> | undefined) {
  const e = entry ?? {}
  const model = typeof e.model_config_id === 'string' ? e.model_config_id : ''
  Object.assign(form, {
    enabled: e.enabled === true,
    model_config_id: props.models.some((m) => m.id === model) ? model : '',
    depth: count(e.depth, DEFAULTS.depth),
    episode_limit: count(e.episode_limit, DEFAULTS.episode_limit),
    summary_limit: count(e.summary_limit, DEFAULTS.summary_limit),
  })
}

function snapshot(): Record<string, unknown> {
  return { ...form }
}

async function apply(chatId: string) {
  if (!form.enabled) return
  await recallApi.setup(chatId, { ...form, model_config_id: form.model_config_id || null })
}
defineExpose({ apply, snapshot, restore })
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
