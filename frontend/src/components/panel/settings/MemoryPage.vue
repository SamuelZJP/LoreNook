<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ChatDetail } from '@/api/endpoints'
import InfoTip from '@/components/InfoTip.vue'
import { useSaveTracker } from '@/composables/autosave'
import { useChatPatch } from './chatPatch'

/** How much of the story the AI reads in full. Recall adds its block below. */
const props = defineProps<{ chat: ChatDetail }>()
const tracker = useSaveTracker()
const patch = useChatPatch(() => props.chat.id)

const recent = ref(props.chat.recent_rounds)
const minSummaries = ref(props.chat.min_summaries)
watch(() => props.chat.recent_rounds, (v) => (recent.value = v))
watch(() => props.chat.min_summaries, (v) => (minSummaries.value = v))

const valid = (n: unknown): n is number => Number.isInteger(n) && (n as number) >= 0
function setRecent(delay = 600) {
  if (valid(recent.value)) tracker.schedule('recent_rounds', () => patch({ recent_rounds: recent.value }), delay)
}
function setMin(delay = 600) {
  if (valid(minSummaries.value)) tracker.schedule('min_summaries', () => patch({ min_summaries: minSummaries.value }), delay)
}
</script>

<template>
  <div class="stack">
    <div class="row tip-row">
      <h3>记得多少</h3>
      <InfoTip>最近的若干回合以原文交给 AI，更早的压缩成摘要和情节。原文越多越连贯，也越耗费额度。</InfoTip>
    </div>
    <div class="grid-2">
      <div class="field">
        <label>保留原文的回合</label>
        <input v-model.number="recent" class="input" type="number" min="0" step="1" :aria-invalid="!valid(recent)" @input="setRecent()" @blur="setRecent(0)" />
      </div>
      <div class="field">
        <label>至少保留的摘要</label>
        <input v-model.number="minSummaries" class="input" type="number" min="0" step="1" :aria-invalid="!valid(minSummaries)" @input="setMin()" @blur="setMin(0)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tip-row { gap: var(--space-1); }
</style>
