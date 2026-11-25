<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { isDemo } from '@/features/account/session'
import { demoApi } from './api'

// Polled, so allowances spent by writing and drawing show without wiring into those flows.
const query = useQuery({ queryKey: ['demo-status'], queryFn: demoApi.status, enabled: isDemo, refetchInterval: 30_000 })
const now = ref(Date.now())
const timer = window.setInterval(() => (now.value = Date.now()), 15_000)
onBeforeUnmount(() => window.clearInterval(timer))

const minutes = computed(() => {
  const ends = query.data.value?.expires_at
  return ends ? Math.max(0, Math.ceil((Date.parse(ends) - now.value) / 60_000)) : null
})
</script>

<template>
  <div v-if="isDemo && query.data.value" class="demo-banner" role="status">
    <strong>体验账号</strong>
    <span>剩余 {{ minutes }} 分钟 · 写作 {{ query.data.value.rounds_left }} 次 · 生图 {{ query.data.value.images_left }} 张</span>
  </div>
</template>

<style scoped>
.demo-banner {
  display: flex; flex-direction: column; gap: 2px; padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border); font-size: var(--text-xs); color: var(--text-muted); line-height: 1.5;
}
.demo-banner strong { color: var(--accent); font-weight: 600; }
</style>
