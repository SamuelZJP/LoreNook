<script setup lang="ts">
defineProps<{ chatId: string | null; what: string }>()
</script>

<template>
  <div class="scope" :class="chatId ? 'chat' : 'source'">
    <template v-if="chatId">正在编辑<strong>本聊天的{{ what }}副本</strong>。修改只影响这个聊天，不会改动资源库。</template>
    <template v-else>正在编辑<strong>资源库中的{{ what }}</strong>。修改不会影响已创建的聊天，新聊天创建时才会复制。</template>
  </div>
</template>

<style scoped>
.scope { font-size: 12px; padding: 6px 10px; border-radius: var(--radius-s); }
.scope.chat { background: var(--accent-soft); }
.scope.source { background: var(--bg-sunken); color: var(--text-muted); }
</style>
