<script setup lang="ts">
import { Lock } from 'lucide-vue-next'
import InfoTip from '../InfoTip.vue'

/** Marks a chat-owned copy. Library records need no note. */
defineProps<{ chatId: string | null; what: string }>()
</script>

<template>
  <div v-if="chatId" class="scope row">
    <span class="badge accent"><Lock /> 仅本聊天</span>
    <InfoTip>这是本聊天自己的{{ what }}，修改不会影响资源库或其他聊天。</InfoTip>
  </div>
</template>

<style scoped>
.scope { gap: var(--space-1); }
.badge svg { width: 12px; height: 12px; }
</style>
