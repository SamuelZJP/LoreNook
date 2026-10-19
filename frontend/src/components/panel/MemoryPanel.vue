<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { RefreshCw, Eye, FileJson } from 'lucide-vue-next'
import { api, type ChatDetail } from '@/api/endpoints'
import type { RoundFlow } from '@/composables/roundFlow'
import ErrorBox from '../ErrorBox.vue'
import CodeEditor from '../CodeEditor.vue'
import { contentBody } from '@/lib/sections'
import { pretty } from '@/lib/format'

const props = defineProps<{ chat: ChatDetail; flow: RoundFlow }>()
const memory = useQuery({ queryKey: computed(() => ['memory', props.chat.id]), queryFn: () => api.memory(props.chat.id) })

const counts = computed(() => {
  const items = memory.data.value?.items ?? []
  return {
    episode: items.filter((i) => i.kind === 'episode').length,
    summary: items.filter((i) => i.kind === 'summary').length,
    round: items.filter((i) => i.kind === 'round').length,
  }
})

const resolved = ref<Awaited<ReturnType<typeof api.resolveDefinitions>> | null>(null)
const resolveError = ref<unknown>(null)
async function resolve() {
  resolveError.value = null
  resolved.value = null
  try {
    resolved.value = await api.resolveDefinitions(props.chat.id)
  } catch (e) {
    resolveError.value = e
  }
}

const preview = ref<string | null>(null)
const previewError = ref<unknown>(null)
const previewing = ref(false)
async function writingPreview() {
  previewError.value = null
  preview.value = null
  previewing.value = true
  try {
    const r = await api.writingPreview(props.chat.id, props.flow.input.value)
    preview.value = pretty(r.request)
  } catch (e) {
    previewError.value = e
  } finally {
    previewing.value = false
  }
}
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3 class="grow">写作上下文中的历史</h3>
      <button class="btn ghost icon small" type="button" title="刷新" @click="memory.refetch()"><RefreshCw /></button>
    </div>
    <p class="hint">由后端按 X / Y 和已保存情节选择，每个已归档回合只使用一种表示。这里只读。</p>
    <ErrorBox v-if="memory.error.value" :error="memory.error.value" />
    <template v-if="memory.data.value">
      <div class="row wrap">
        <span class="badge">共 {{ memory.data.value.total_rounds }} 回合</span>
        <span class="badge">X = {{ memory.data.value.recent_rounds }}</span>
        <span class="badge">Y = {{ memory.data.value.min_summaries }}</span>
        <span class="badge accent">情节 {{ counts.episode }}</span>
        <span class="badge accent">摘要 {{ counts.summary }}</span>
        <span class="badge accent">完整 {{ counts.round }}</span>
        <span v-if="memory.data.value.uses_compressed_history" class="badge warn">使用压缩历史</span>
      </div>
      <div v-if="!memory.data.value.items.length" class="empty">还没有已归档的回合</div>
      <ol class="items">
        <li v-for="item in memory.data.value.items" :key="item.kind + item.id" :class="item.kind">
          <template v-if="item.kind === 'episode'">
            <div class="kind">情节 · 第 {{ item.start_round_no }}–{{ item.end_round_no }} 回合 · {{ item.title }}</div>
            <p class="text">{{ item.summary }}</p>
          </template>
          <template v-else-if="item.kind === 'summary'">
            <div class="kind">摘要 · 第 {{ item.round_no }} 回合</div>
            <p class="text">{{ item.summary }}</p>
          </template>
          <template v-else>
            <div class="kind">完整 · 第 {{ item.round_no }} 回合</div>
            <p class="text clamp"><strong>输入：</strong>{{ item.user_input || '（空）' }}</p>
            <p class="text clamp"><strong>输出：</strong>{{ contentBody(item.ai_output) }}</p>
          </template>
        </li>
      </ol>
    </template>

    <h3>诊断</h3>
    <div class="row wrap">
      <button class="btn small" type="button" @click="resolve"><Eye /> 定义渲染结果</button>
      <button class="btn small" type="button" :disabled="previewing" @click="writingPreview"><FileJson /> {{ previewing ? '构建中…' : '写作请求预览' }}</button>
    </div>
    <p class="hint">写作请求预览使用当前输入框内容和已选预设构建请求，不调用模型，也不合并模型默认参数。</p>
    <ErrorBox v-if="resolveError" :error="resolveError" title="定义渲染失败" />
    <div v-if="resolved" class="stack tight">
      <div class="label">角色定义（{{ (resolved.character_definitions ?? []).length }}）</div>
      <pre v-for="d in resolved.character_definitions ?? []" :key="d.id" class="block">{{ d.content }}</pre>
      <div class="label">用户定义（{{ (resolved.user_definitions ?? []).length }}）</div>
      <pre v-for="d in resolved.user_definitions ?? []" :key="d.id" class="block">{{ d.content }}</pre>
    </div>
    <ErrorBox v-if="previewError" :error="previewError" title="预览失败" />
    <CodeEditor v-if="preview" :model-value="preview" language="json" readonly min-height="200px" />
  </div>
</template>

<style scoped>
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.items li { padding: 8px 10px; border-radius: var(--radius-s); background: var(--bg-sunken); border-left: 3px solid var(--border-strong); }
.items li.episode { border-left-color: var(--accent); }
.items li.summary { border-left-color: var(--warn); }
.items li.round { border-left-color: var(--ok); }
.kind { font-size: 12px; font-weight: 600; color: var(--text-muted); }
.text { font-size: 13px; white-space: pre-wrap; word-break: break-word; }
.clamp { display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.block { padding: 8px; background: var(--bg-sunken); border-radius: var(--radius-s); font-size: 12px; max-height: 200px; overflow: auto; }
</style>
