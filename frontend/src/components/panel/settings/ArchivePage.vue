<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { ChatDetail, ModelPurpose } from '@/api/endpoints'
import InfoTip from '@/components/InfoTip.vue'
import { PURPOSE_LABELS } from '@/lib/archive'
import { useSaveTracker } from '@/composables/autosave'
import { ARCHIVE_PURPOSES, bindingsWith, useChatPatch } from './chatPatch'

/** The models behind the steps that run after each confirmed round. */
const props = defineProps<{ chat: ChatDetail }>()
const tracker = useSaveTracker()
const patch = useChatPatch(() => props.chat.id)

const form = reactive(Object.fromEntries(ARCHIVE_PURPOSES.map((p) => [p, props.chat.model_bindings[p] ?? ''])) as Record<string, string>)
for (const p of ARCHIVE_PURPOSES) watch(() => props.chat.model_bindings[p], (v) => (form[p] = v ?? ''))

function set(p: ModelPurpose) {
  tracker.schedule(`binding_${p}`, () => patch({ model_bindings: bindingsWith(props.chat, p, form[p]) }))
}
</script>

<template>
  <div class="stack">
    <div class="row tip-row">
      <h3>整理用的模型</h3>
      <InfoTip>每确认一个回合，后台会更新状态、写回合摘要，必要时写情节摘要。便宜快速的模型通常就够了。</InfoTip>
    </div>
    <div v-for="p in ARCHIVE_PURPOSES" :key="p" class="field">
      <label>{{ PURPOSE_LABELS[p] }}</label>
      <select v-model="form[p]" class="select" @change="set(p)">
        <option value="">（未选择）</option>
        <option v-for="m in chat.model_configs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.tip-row { gap: var(--space-1); }
</style>
