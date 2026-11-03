<script setup lang="ts">
import { computed } from 'vue'
import { Gauge } from 'lucide-vue-next'
import type { RoundRead } from '@/api/endpoints'
import { useChatStatusBar } from '../useChatStatusBar'

/** Opens an earlier round's status bar; the latest round's is always shown. */
const props = defineProps<{ round: RoundRead }>()
const s = useChatStatusBar()
const offered = computed(() => s.active.value && props.round.archive_step !== 'state_update' && props.round.id !== s.latestId.value)
</script>

<template>
  <button v-if="offered" class="btn ghost small" type="button" :aria-pressed="s.opened.has(round.id)" @click="s.toggle(round.id)">
    <Gauge /> {{ s.opened.has(round.id) ? '收起状态栏' : '状态栏' }}
  </button>
</template>
