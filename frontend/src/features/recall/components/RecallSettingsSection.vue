<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save } from 'lucide-vue-next'
import type { ModelConfig } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import { toast } from '@/composables/toast'
import { recallApi, type RecallSettings } from '../api'

/** A chat's recall settings. Saves on its own, separately from the rest of the chat. */
const props = defineProps<{ chatId: string; modelConfigs: ModelConfig[] }>()
const qc = useQueryClient()
const settings = useQuery({ queryKey: computed(() => ['recall-settings', props.chatId]), queryFn: () => recallApi.settings(props.chatId) })

const form = reactive({ model_config_id: '', depth: 3 })
watch(() => settings.data.value, (s) => {
  if (!s) return
  form.model_config_id = s.model_config_id ?? ''
  form.depth = s.depth ?? 3
}, { immediate: true })

const body = computed<RecallSettings>(() => ({ model_config_id: form.model_config_id || null, depth: form.depth }))
const dirty = computed(() => {
  const s = settings.data.value
  return !!s && (body.value.model_config_id !== (s.model_config_id ?? null) || body.value.depth !== s.depth)
})

const saving = ref(false)
const error = ref<unknown>(null)
async function save() {
  saving.value = true
  error.value = null
  try {
    qc.setQueryData(['recall-settings', props.chatId], await recallApi.putSettings(props.chatId, body.value))
    toast('记忆召回设置已保存')
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="stack">
    <h3>记忆召回</h3>
    <ErrorBox v-if="settings.error.value" :error="settings.error.value" title="读取失败" />
    <div class="grid-2">
      <div class="field">
        <label>召回模型</label>
        <select v-model="form.model_config_id" class="select">
          <option value="">（关闭召回）</option>
          <option v-for="m in modelConfigs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
        </select>
      </div>
      <div class="field">
        <label>回忆深度</label>
        <input v-model.number="form.depth" class="input" type="number" min="0" step="1" />
      </div>
    </div>
    <p class="hint">每次发送时，以最近若干个完整回合和最新输入为依据，就地展开相关的情节和摘要。</p>
    <ErrorBox v-if="error" :error="error" title="保存失败" />
    <div class="row">
      <button class="btn small" type="button" :disabled="!dirty || saving" @click="save"><Save /> 保存记忆召回设置</button>
    </div>
  </div>
</template>
