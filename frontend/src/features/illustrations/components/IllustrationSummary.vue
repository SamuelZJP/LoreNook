<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { ChatDetail } from '@/api/endpoints'
import { illustrationApi } from '../api'
import { MODE_LABELS } from '../lib'

/** The illustration row's summary: when pictures are made, and whether anything is missing. */
const props = defineProps<{ chat: ChatDetail }>()
const settings = useQuery({ queryKey: computed(() => ['illustration-settings', props.chat.id]), queryFn: () => illustrationApi.settings(props.chat.id) })
const mode = computed(() => settings.data.value?.mode ?? 'off')
const label = computed(() => MODE_LABELS[mode.value].replace(/（.*）$/, ''))
const missing = computed(() => mode.value !== 'off' && !settings.data.value?.image_workflow_id)
</script>

<template>
  <span v-if="settings.data.value">{{ label }}<span v-if="missing" class="warn"> · 未选工作流</span></span>
</template>

<style scoped>
.warn { color: var(--warn); }
</style>
