<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { ChatDetail } from '@/api/endpoints'
import { recallApi } from '../api'

/** Recall's part of the memory row summary. */
const props = defineProps<{ chat: ChatDetail }>()
const settings = useQuery({ queryKey: computed(() => ['recall-settings', props.chat.id]), queryFn: () => recallApi.settings(props.chat.id) })
</script>

<template>
  <span v-if="settings.data.value">{{ settings.data.value.enabled ? '召回已开' : '召回关闭' }}</span>
</template>
