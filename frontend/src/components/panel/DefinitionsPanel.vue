<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { RefreshCw, ChevronRight, ChevronsUpDown } from 'lucide-vue-next'
import { api, type ChatDetail } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'

const props = defineProps<{ chat: ChatDetail }>()
const resolved = useQuery({
  queryKey: computed(() => ['definitions-resolved', props.chat.id]),
  queryFn: () => api.resolveDefinitions(props.chat.id),
  staleTime: 0,
})
const groups = computed(() => [
  { id: 'character', label: '角色定义', items: resolved.data.value?.character_definitions ?? [] },
  { id: 'user', label: '用户定义', items: resolved.data.value?.user_definitions ?? [] },
])
const allKeys = computed(() => groups.value.flatMap((g) => g.items.map((d) => g.id + d.id)))

const open = ref(new Set<string>())
function toggle(key: string) {
  const next = new Set(open.value)
  if (!next.delete(key)) next.add(key)
  open.value = next
}
const allOpen = computed(() => allKeys.value.length > 0 && allKeys.value.every((k) => open.value.has(k)))
function toggleAll() {
  open.value = allOpen.value ? new Set() : new Set(allKeys.value)
}
const firstLine = (content: string) => content.trim().split('\n', 1)[0] || '（空）'
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3 class="grow">定义渲染结果</h3>
      <button class="btn ghost icon small" type="button" :title="allOpen ? '全部收起' : '全部展开'" :disabled="!allKeys.length" @click="toggleAll"><ChevronsUpDown /></button>
      <button class="btn ghost icon small" type="button" title="刷新" :disabled="resolved.isFetching.value" @click="resolved.refetch()"><RefreshCw /></button>
    </div>
    <p class="hint">按当前状态渲染本聊天的角色定义和用户定义。这里只读。</p>
    <ErrorBox v-if="resolved.error.value" :error="resolved.error.value" title="定义渲染失败" />
    <div v-else-if="resolved.isPending.value" class="empty">渲染中…</div>
    <template v-else>
      <template v-for="g in groups" :key="g.id">
        <div class="label">{{ g.label }}（{{ g.items.length }}）</div>
        <div v-if="!g.items.length" class="empty">无</div>
        <ol v-else class="items">
          <li v-for="(d, i) in g.items" :key="d.id" :class="[g.id, { open: open.has(g.id + d.id) }]">
            <button class="head" type="button" :aria-expanded="open.has(g.id + d.id)" @click="toggle(g.id + d.id)">
              <ChevronRight class="chevron" />
              <span class="kind">#{{ i + 1 }}</span>
              <span class="preview">{{ firstLine(d.content) }}</span>
            </button>
            <pre v-if="open.has(g.id + d.id)" class="body">{{ d.content }}</pre>
          </li>
        </ol>
      </template>
    </template>
  </div>
</template>

<style scoped>
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.items li { border-radius: var(--radius-s); background: var(--bg-sunken); border-left: 3px solid var(--border-strong); }
.items li.character { border-left-color: var(--accent); }
.items li.user { border-left-color: var(--ok); }
.head {
  display: flex; align-items: center; gap: var(--space-1-5); width: 100%; height: 34px; padding: 0 var(--space-2);
  border: 0; background: none; color: inherit; font: inherit; font-size: var(--text-xs); text-align: left; cursor: pointer;
}
.head:hover { background: var(--bg-hover); }
.chevron { width: 14px; height: 14px; flex: none; color: var(--text-muted); transition: transform 0.15s; }
.open .chevron { transform: rotate(90deg); }
.kind { flex: none; font-weight: 600; }
.preview { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); }
.open .preview { visibility: hidden; }
.body { margin: 0; padding: 0 var(--space-3) var(--space-3) 28px; font-size: var(--text-xs); white-space: pre-wrap; word-break: break-word; }
</style>
