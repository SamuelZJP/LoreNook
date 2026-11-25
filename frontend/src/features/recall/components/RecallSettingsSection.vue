<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { ChatDetail } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import InfoTip from '@/components/InfoTip.vue'
import { useSaveTracker } from '@/composables/autosave'
import { recallApi, type RecallSettings } from '../api'

/** A chat's recall settings, saved as they change. Shown inside the chat's memory settings. */
const props = defineProps<{ chat: ChatDetail }>()
const qc = useQueryClient()
const tracker = useSaveTracker()
const settings = useQuery({ queryKey: computed(() => ['recall-settings', props.chat.id]), queryFn: () => recallApi.settings(props.chat.id) })

const form = reactive({ enabled: false, model_config_id: '', depth: 3, episode_limit: 2, summary_limit: 5 })
// The form is filled once; after that it leads, so a save returning late can't undo newer edits.
let loaded = false
watch(() => settings.data.value, (s) => {
  if (!s || loaded) return
  loaded = true
  Object.assign(form, {
    enabled: s.enabled ?? false, model_config_id: s.model_config_id ?? '',
    depth: s.depth ?? 3, episode_limit: s.episode_limit ?? 2, summary_limit: s.summary_limit ?? 5,
  })
}, { immediate: true })

const valid = computed(() => [form.depth, form.episode_limit, form.summary_limit].every((n) => Number.isInteger(n) && n >= 0))
function save(delay: number) {
  if (!loaded || !valid.value) return
  tracker.schedule('recall', async () => {
    const body: RecallSettings = { ...form, model_config_id: form.model_config_id || null }
    qc.setQueryData(['recall-settings', props.chat.id], await recallApi.putSettings(props.chat.id, body))
  }, delay)
}
</script>

<template>
  <div class="stack">
    <div class="row tip-row">
      <h3>记忆召回</h3>
      <InfoTip>每次发送前，根据最近的剧情把相关的旧情节和摘要临时展开给 AI。上限是每次最多展开的条数。</InfoTip>
      <span class="grow" />
      <input v-model="form.enabled" type="checkbox" class="switch" aria-label="启用记忆召回" @change="save(0)" />
    </div>
    <ErrorBox v-if="settings.error.value" :error="settings.error.value" title="读取失败" />
    <template v-if="form.enabled">
      <div class="field">
        <label>召回模型</label>
        <select v-model="form.model_config_id" class="select" @change="save(0)">
          <option value="">（未选择）</option>
          <option v-for="m in chat.model_configs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
        </select>
      </div>
      <p v-if="!form.model_config_id" class="hint warn">选择召回模型后才会生效。</p>
      <div class="grid-3">
        <div class="field">
          <label>回忆深度</label>
          <input v-model.number="form.depth" class="input" type="number" min="0" step="1" @input="save(600)" @blur="save(0)" />
        </div>
        <div class="field">
          <label>情节上限</label>
          <input v-model.number="form.episode_limit" class="input" type="number" min="0" step="1" @input="save(600)" @blur="save(0)" />
        </div>
        <div class="field">
          <label>摘要上限</label>
          <input v-model.number="form.summary_limit" class="input" type="number" min="0" step="1" @input="save(600)" @blur="save(0)" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tip-row { gap: var(--space-1); }
.grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
</style>
