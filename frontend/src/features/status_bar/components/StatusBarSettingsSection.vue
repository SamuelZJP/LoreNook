<script setup lang="ts">
import { computed } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { ChatDetail } from '@/api/endpoints'
import { useSaveTracker } from '@/composables/autosave'
import { statusBarApi } from '../api'

/** The status bar row's inline switch. Only offered when the chat's character has code. */
const props = defineProps<{ chat: ChatDetail }>()
const qc = useQueryClient()
const tracker = useSaveTracker()
const bar = useQuery({ queryKey: computed(() => ['status-bar', props.chat.id]), queryFn: () => statusBarApi.chat(props.chat.id) })
const hasCode = computed(() => !!bar.data.value?.code.trim())

function setEnabled(enabled: boolean) {
  tracker.schedule('status-bar', async () => {
    qc.setQueryData(['status-bar', props.chat.id], await statusBarApi.patchChat(props.chat.id, { enabled }))
  })
}
</script>

<template>
  <span v-if="bar.data.value && !hasCode" class="faint">角色没有状态栏</span>
  <input
    v-else-if="bar.data.value" type="checkbox" class="switch" aria-label="在回复底部显示状态栏"
    :checked="bar.data.value.enabled" @click.stop @change="setEnabled(($event.target as HTMLInputElement).checked)"
  />
</template>
