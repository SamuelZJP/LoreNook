<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ChatDetail } from '@/api/endpoints'
import InfoTip from '@/components/InfoTip.vue'
import { useSaveTracker } from '@/composables/autosave'
import { bindingsWith, useChatPatch } from './chatPatch'

/** Which writing style and which model write this chat. */
const props = defineProps<{ chat: ChatDetail }>()
const tracker = useSaveTracker()
const patch = useChatPatch(() => props.chat.id)

const preset = ref(props.chat.writing_preset_id ?? '')
const model = ref(props.chat.model_bindings.writing ?? '')
watch(() => props.chat.writing_preset_id, (v) => (preset.value = v ?? ''))
watch(() => props.chat.model_bindings.writing, (v) => (model.value = v ?? ''))

function setPreset() {
  tracker.schedule('writing_preset', () => patch({ writing_preset_id: preset.value || null }))
}
function setModel() {
  tracker.schedule('writing_model', () => patch({ model_bindings: bindingsWith(props.chat, 'writing', model.value) }))
}
</script>

<template>
  <div class="stack">
    <div class="field">
      <label>写作风格</label>
      <select v-model="preset" class="select" @change="setPreset">
        <option value="">（未选择）</option>
        <option v-for="p in chat.writing_presets" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
    </div>
    <div class="field">
      <div class="row tip-row">
        <label class="label">写作模型</label>
        <InfoTip>模型的接口类型需与写作风格一致。可在“幕后 › 本聊天资源”中添加。</InfoTip>
      </div>
      <select v-model="model" class="select" @change="setModel">
        <option value="">（未选择）</option>
        <option v-for="m in chat.model_configs" :key="m.id" :value="m.id">{{ m.name }} · {{ m.model }}</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.tip-row { gap: var(--space-1); }
</style>
