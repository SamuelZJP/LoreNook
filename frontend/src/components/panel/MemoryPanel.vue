<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { RefreshCw, ChevronRight, ChevronsUpDown } from 'lucide-vue-next'
import { api, type ChatDetail, type ChatMemory } from '@/api/endpoints'
import ErrorBox from '../ErrorBox.vue'
import { contentBody } from '@/lib/sections'

/** `timeline` replaces the assembled history for the current request; what differs is highlighted. */
const props = defineProps<{ chat: ChatDetail; timeline?: ChatMemory | null; preparing?: string }>()
const memory = useQuery({ queryKey: computed(() => ['memory', props.chat.id]), queryFn: () => api.memory(props.chat.id) })

type Item = NonNullable<typeof memory.data.value>['items'][number]
const shown = computed(() => props.timeline ?? memory.data.value)
const items = computed(() => shown.value?.items ?? [])
const counts = computed(() => ({
  episode: items.value.filter((i) => i.kind === 'episode').length,
  summary: items.value.filter((i) => i.kind === 'summary').length,
  round: items.value.filter((i) => i.kind === 'round').length,
}))

const keyOf = (item: Item) => item.kind + item.id
const expanded = computed(() => {
  if (!props.timeline || !memory.data.value) return new Set<string>()
  const assembled = new Set(memory.data.value.items.map(keyOf))
  return new Set(items.value.map(keyOf).filter((k) => !assembled.has(k)))
})
const open = ref(new Set<string>())
function toggle(item: Item) {
  const next = new Set(open.value)
  const k = keyOf(item)
  if (!next.delete(k)) next.add(k)
  open.value = next
}
const allOpen = computed(() => items.value.length > 0 && items.value.every((i) => open.value.has(keyOf(i))))
function toggleAll() {
  open.value = allOpen.value ? new Set() : new Set(items.value.map(keyOf))
}

const kindLabel = { episode: '情节', summary: '摘要', round: '完整' } as const
function rangeOf(item: Item) {
  return item.kind === 'episode' ? `第 ${item.start_round_no}–${item.end_round_no} 回合` : `第 ${item.round_no} 回合`
}
function previewOf(item: Item) {
  if (item.kind === 'episode') return item.title
  if (item.kind === 'summary') return item.summary
  return item.user_input || '（空）'
}
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3 class="grow">写作上下文中的历史</h3>
      <button class="btn ghost icon small" type="button" :title="allOpen ? '全部收起' : '全部展开'" :disabled="!items.length" @click="toggleAll"><ChevronsUpDown /></button>
      <button class="btn ghost icon small" type="button" title="刷新" @click="memory.refetch()"><RefreshCw /></button>
    </div>
    <p class="hint">由后端选择，每个已归档回合只使用一种表示。高亮的是本次发送时展开的记忆。这里只读。</p>
    <ErrorBox v-if="memory.error.value" :error="memory.error.value" />
    <template v-if="shown">
      <div class="row wrap">
        <span class="badge">共 {{ shown.total_rounds }} 回合</span>
        <span class="badge accent">情节 {{ counts.episode }}</span>
        <span class="badge accent">摘要 {{ counts.summary }}</span>
        <span class="badge accent">完整 {{ counts.round }}</span>
        <span v-if="preparing" class="badge">{{ preparing }}</span>
        <span v-else-if="expanded.size" class="badge accent">本次展开 {{ expanded.size }}</span>
      </div>
      <div v-if="!items.length" class="empty">还没有已归档的回合</div>
      <ol class="items">
        <li v-for="item in items" :key="keyOf(item)" :class="[item.kind, { open: open.has(keyOf(item)), expanded: expanded.has(keyOf(item)) }]">
          <button class="head" type="button" :aria-expanded="open.has(keyOf(item))" @click="toggle(item)">
            <ChevronRight class="chevron" />
            <span class="kind">{{ kindLabel[item.kind] }}</span>
            <span class="range">{{ rangeOf(item) }}</span>
            <span class="preview">{{ previewOf(item) }}</span>
          </button>
          <div v-if="open.has(keyOf(item))" class="body">
            <template v-if="item.kind === 'episode'">
              <p class="text"><strong>{{ item.title }}</strong></p>
              <p class="text">{{ item.summary }}</p>
            </template>
            <p v-else-if="item.kind === 'summary'" class="text">{{ item.summary }}</p>
            <template v-else>
              <p class="text"><strong>输入：</strong>{{ item.user_input || '（空）' }}</p>
              <p class="text"><strong>输出：</strong>{{ contentBody(item.ai_output) }}</p>
            </template>
          </div>
        </li>
      </ol>
    </template>
  </div>
</template>

<style scoped>
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.items li { border-radius: var(--radius-s); background: var(--bg-sunken); border-left: 3px solid var(--border-strong); }
.items li.episode { border-left-color: var(--accent); }
.items li.summary { border-left-color: var(--warn); }
.items li.round { border-left-color: var(--ok); }
.items li.expanded { background: var(--accent-soft); }
.head {
  display: flex; align-items: center; gap: 6px; width: 100%; height: 34px; padding: 0 8px;
  border: 0; background: none; color: inherit; font: inherit; font-size: 12px; text-align: left; cursor: pointer;
}
.head:hover { background: var(--bg-hover); }
.chevron { width: 14px; height: 14px; flex: none; color: var(--text-muted); transition: transform 0.15s; }
.open .chevron { transform: rotate(90deg); }
.kind { flex: none; font-weight: 600; }
.range { flex: none; color: var(--text-muted); }
.preview { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); }
.open .preview { visibility: hidden; }
.body { display: flex; flex-direction: column; gap: 6px; padding: 0 10px 10px 28px; }
.text { margin: 0; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
</style>
