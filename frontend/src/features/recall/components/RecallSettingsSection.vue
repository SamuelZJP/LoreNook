<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Save } from 'lucide-vue-next'
import type { ModelConfig } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import InfoTip from '@/components/InfoTip.vue'
import { toast } from '@/composables/toast'
import { recallApi, type RecallSettings } from '../api'

/** A chat's recall settings. Saves on its own, separately from the rest of the chat. */
const props = defineProps<{ chatId: string; modelConfigs: ModelConfig[] }>()
const qc = useQueryClient()
const settings = useQuery({ queryKey: computed(() => ['recall-settings', props.chatId]), queryFn: () => recallApi.settings(props.chatId) })

const form = reactive({ enabled: false, model_config_id: '', depth: 3, episode_limit: 2, summary_limit: 5 })
watch(() => settings.data.value, (s) => {
  if (!s) return
  form.enabled = s.enabled ?? false
  form.model_config_id = s.model_config_id ?? ''
  form.depth = s.depth ?? 3
  form.episode_limit = s.episode_limit ?? 2
  form.summary_limit = s.summary_limit ?? 5
}, { immediate: true })

const body = computed<RecallSettings>(() => ({ ...form, model_config_id: form.model_config_id || null }))
const dirty = computed(() => {
  const s = settings.data.value
  return !!s && JSON.stringify(body.value) !== JSON.stringify({
    enabled: s.enabled, model_config_id: s.model_config_id ?? null, depth: s.depth, episode_limit: s.episode_limit, summary_limit: s.summary_limit,
  })
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
    <div class="row">
      <h3>记忆召回</h3>
      <InfoTip>每次发送前，根据最近的剧情把相关的旧情节和摘要临时展开给 AI。上限是每次最多展开的条数。</InfoTip>
    </div>
    <ErrorBox v-if="settings.error.value" :error="settings.error.value" title="读取失败" />
    <label class="check"><input v-model="form.enabled" type="checkbox" /> 启用记忆召回</label>
    <div class="grid-2">
      <div class="field">
        <label>召回模型</label>
        <select v-model="form.model_config_id" class="select">
          <option value="">（未选择）</option>
          <option v-for="m in modelConfigs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
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
    <p v-if="form.enabled && !form.model_config_id" class="hint warn">选择召回模型后才会生效。</p>
    <ErrorBox v-if="error" :error="error" title="保存失败" />
    <div class="row">
      <button class="btn small" type="button" :disabled="!dirty || saving" @click="save"><Save /> 保存记忆召回设置</button>
    </div>
  </div>
</template>
