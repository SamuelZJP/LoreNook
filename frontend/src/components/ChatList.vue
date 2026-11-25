<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useRoute } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import AvatarBadge from './AvatarBadge.vue'
import ErrorBox from './ErrorBox.vue'
import { formatShortTime, formatTime } from '@/lib/format'

const route = useRoute()
const filter = ref('')
const { data, error, isLoading } = useQuery({ queryKey: ['chats'], queryFn: api.chats })
const chats = computed(() => {
  const q = filter.value.trim().toLowerCase()
  return (data.value ?? []).filter((c) => !q || c.title.toLowerCase().includes(q))
})
</script>

<template>
  <div class="chat-list">
    <label class="search">
      <Search />
      <input v-model="filter" class="input" placeholder="搜索聊天" />
    </label>
    <ErrorBox v-if="error" :error="error" title="无法读取聊天列表" />
    <div v-else-if="isLoading" class="empty">加载中…</div>
    <div v-else-if="!chats.length" class="empty">{{ filter ? '没有匹配的聊天' : '还没有聊天' }}</div>
    <template v-else>
      <div class="section-label">最近</div>
      <nav class="items">
        <RouterLink
          v-for="chat in chats" :key="chat.id" :to="`/chats/${chat.id}`"
          class="item" :class="{ active: route.params.id === chat.id }"
        >
          <AvatarBadge class="av" :name="chat.title" :src="chat.avatar" :size="42" />
          <span class="ellipsis title">{{ chat.title }}</span>
          <time class="time" :datetime="chat.created_at" :title="formatTime(chat.created_at)">{{ formatShortTime(chat.created_at) }}</time>
          <span class="ellipsis line">{{ chat.last_line || '还没有内容' }}</span>
        </RouterLink>
      </nav>
    </template>
  </div>
</template>

<style scoped>
.search { position: relative; display: block; margin-bottom: var(--space-2); }
.search svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); width: 15px; height: 15px; color: var(--text-faint); }
.search .input { min-height: 38px; padding-left: var(--space-8); background: var(--bg-sunken); border-color: transparent; }
.section-label { padding: var(--space-2) var(--space-2) var(--space-1-5); font-size: var(--text-xs); font-weight: 600; color: var(--text-faint); letter-spacing: 0.04em; }
.items { display: flex; flex-direction: column; gap: var(--space-0-5); }
/* Avatar on the left; name and time on top, the latest line below. */
.item {
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto; column-gap: var(--space-3); row-gap: 1px; align-items: center;
  padding: var(--space-2); border-radius: var(--radius-l); color: inherit; text-decoration: none;
}
.item:hover { background: var(--bg-hover); }
.item.active { background: var(--bg-active); }
.av { grid-row: span 2; }
.title { font-weight: 600; }
.time { font-size: var(--text-xs); color: var(--text-faint); font-variant-numeric: tabular-nums; }
.line { grid-column: 2 / 4; font-size: var(--text-sm); color: var(--text-muted); }
</style>
