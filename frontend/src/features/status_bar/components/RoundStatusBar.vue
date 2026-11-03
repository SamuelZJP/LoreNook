<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { RoundRead } from '@/api/endpoints'
import ErrorBox from '@/components/ErrorBox.vue'
import { statusBarApi } from '../api'
import { useChatStatusBar } from '../useChatStatusBar'
import StatusBarFrame from './StatusBarFrame.vue'

/** The status bar at the foot of a round's reading page: the latest round's always, others when opened. */
const props = defineProps<{ round: RoundRead }>()
const s = useChatStatusBar()
const latest = computed(() => props.round.id === s.latestId.value)
const shown = computed(() => s.active.value && props.round.archive_step !== 'state_update' && s.isOpen(props.round.id))

// An earlier round's state never changes from the chat view, so it is read once.
const earlier = useQuery({
  queryKey: computed(() => ['round-progress', s.chatId.value, props.round.id]),
  queryFn: () => statusBarApi.round(s.chatId.value, props.round.id),
  enabled: computed(() => shown.value && !latest.value),
  staleTime: Infinity,
})
const state = computed(() => (latest.value ? s.latestState.data.value?.content : earlier.data.value?.state?.content) ?? null)
const error = computed(() => (latest.value ? s.latestState.error.value : earlier.error.value))
const data = computed(() => state.value && {
  state: state.value,
  round_no: props.round.round_no,
  character: { name: s.names.value.character },
  identity: { name: s.names.value.identity },
})
</script>

<template>
  <div v-if="shown" class="status-bar">
    <ErrorBox v-if="error" :error="error" title="无法读取状态" />
    <StatusBarFrame v-else-if="data" :code="s.code.value" :data="data" />
  </div>
</template>

<style scoped>
.status-bar { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--page-border); }
</style>
