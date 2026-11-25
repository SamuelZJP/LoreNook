<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { useRoute } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import AvatarBadge from './AvatarBadge.vue'
import ErrorBox from './ErrorBox.vue'
import { formatTime } from '@/lib/format'

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
    <nav v-else class="stack tight">
      <RouterLink
        v-for="chat in chats" :key="chat.id" :to="`/chats/${chat.id}`"
        class="list-item" :class="{ active: route.params.id === chat.id }"
      >
        <AvatarBadge :name="chat.title" :src="chat.avatar" :size="38" />
        <div class="grow">
          <div class="ellipsis title">{{ chat.title }}</div>
          <div class="faint small">{{ formatTime(chat.created_at) }}</div>
        </div>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.search { position: relative; display: block; margin-bottom: var(--space-2); }
.search svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 15px; height: 15px; color: var(--text-faint); }
.search .input { padding-left: var(--space-8); background: var(--bg-sunken); border-color: transparent; }
.title { font-weight: 500; }
.small { font-size: var(--text-xs); }
</style>
