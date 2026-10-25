<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRef, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { PanelRight, Check, Trash2, Code2, Loader2, AlertTriangle, Settings2, ChevronUp } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import { ApiError, isTemplateError } from '@/api/client'
import { useRoundFlow } from '@/composables/roundFlow'
import { contentProblem } from '@/lib/sections'
import { STEP_LABELS } from '@/lib/archive'
import { prefs } from '@/lib/prefs'
import { substituteNames } from '@/lib/format'
import { isWide } from '@/composables/layout'
import TopBar from '@/components/TopBar.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import OutputView from '@/components/chat/OutputView.vue'
import ComposerBar from '@/components/chat/ComposerBar.vue'
import ArchiveBanner from '@/components/chat/ArchiveBanner.vue'
import RoundSummaryBlock from '@/components/chat/RoundSummaryBlock.vue'
import EpisodeCard from '@/components/chat/EpisodeCard.vue'
import ChatPanel from '@/components/panel/ChatPanel.vue'
import type { PanelTab } from '@/components/panel/ChatPanel.vue'

const props = defineProps<{ id: string }>()
const chatId = toRef(props, 'id')

const chat = useQuery({ queryKey: computed(() => ['chat', chatId.value]), queryFn: () => api.chat(chatId.value) })
const rounds = useQuery({ queryKey: computed(() => ['rounds', chatId.value]), queryFn: () => api.rounds(chatId.value) })
const episodes = useQuery({ queryKey: computed(() => ['episodes', chatId.value]), queryFn: () => api.episodes(chatId.value) })
const flow = useRoundFlow(chatId)

const panelOpen = ref(isWide.value && localPanelPref())
const panelTab = ref<PanelTab>('state')
function localPanelPref() {
  try { return localStorage.getItem('lorenook.panel') !== 'closed' } catch { return true }
}
function togglePanel(tab?: typeof panelTab.value) {
  if (tab && (!panelOpen.value || panelTab.value !== tab)) {
    panelTab.value = tab
    panelOpen.value = true
  } else panelOpen.value = !panelOpen.value
  if (isWide.value) try { localStorage.setItem('lorenook.panel', panelOpen.value ? 'open' : 'closed') } catch { /* ignore */ }
}

const character = computed(() => chat.data.value?.character)
const identity = computed(() => chat.data.value?.user_identity)
// A chat-owned character keeps only the scene chosen at creation.
const rawFirstMessage = computed(() => character.value?.scenes[0]?.first_message ?? '')
const firstMessage = computed(() =>
  character.value && identity.value ? substituteNames(rawFirstMessage.value, identity.value.name, character.value.name) : '')
const roundList = computed(() => rounds.data.value ?? [])
const roundNo = computed(() => new Map(roundList.value.map((r) => [r.id, r.round_no])))
const latest = computed(() => roundList.value.at(-1) ?? null)
const latestComplete = computed(() => !latest.value || latest.value.archive_step === 'complete')

// Floor display limit: rendering only. Earlier floors revealed here stay until the chat changes.
const revealed = ref(0)
watch(chatId, () => { revealed.value = 0 })
const shownCount = computed(() => (prefs.floorLimit === null ? Infinity : prefs.floorLimit + revealed.value))
const hiddenFloors = computed(() => Math.max(0, roundList.value.length - shownCount.value))
const shownRounds = computed(() => (hiddenFloors.value ? roundList.value.slice(hiddenFloors.value) : roundList.value))
function loadEarlier() {
  const el = scroller.value
  const fromBottom = el ? el.scrollHeight - el.scrollTop : 0
  revealed.value += prefs.floorLimit ?? 0
  // Keep the floor the reader was looking at in place while earlier floors are inserted above it.
  nextTick(() => { if (el) el.scrollTop = el.scrollHeight - fromBottom })
}

const episodesByEnd = computed(() => {
  const map = new Map<string, NonNullable<typeof episodes.data.value>>()
  for (const ep of episodes.data.value ?? []) {
    const list = map.get(ep.end_round_id) ?? []
    list.push(ep)
    map.set(ep.end_round_id, list)
  }
  return map
})

const readiness = computed(() => {
  const c = chat.data.value
  if (!c) return null
  if (!c.writing_preset_id) return '尚未选择写作预设'
  if (!c.model_bindings.writing) return '尚未绑定写作模型'
  return null
})

const raw = reactive(new Set<string>())
/** Summaries toggled away from the `showSummaries` default. */
const openSummaries = reactive(new Set<string>())
const summaryOpen = (id: string) => prefs.showSummaries !== openSummaries.has(id)
function toggle(set: Set<string>, id: string) {
  if (set.has(id)) set.delete(id)
  else set.add(id)
}

const candidate = flow.candidate
const candidateProblem = computed(() => (candidate.value ? contentProblem(candidate.value.ai_output) : null))
const generateError = computed(() => (flow.error.value?.action === 'generate' ? flow.error.value.error : null))
/** Locate a failed template among the chat's own definitions. */
const templateLocation = computed(() => {
  const e = generateError.value
  const c = chat.data.value
  if (!(e instanceof ApiError) || !isTemplateError(e.detail) || !c) return null
  const id = e.detail.definition_id
  const ci = c.character.definitions.findIndex((d) => d.id === id)
  const ui = c.user_identity.definitions.findIndex((d) => d.id === id)
  const where = ci >= 0 ? `角色定义 #${ci + 1}` : ui >= 0 ? `用户身份定义 #${ui + 1}` : '某条定义'
  return `${where}${e.detail.line ? ` 第 ${e.detail.line} 行` : ''}`
})

// Keep the newest entry in view.
const scroller = ref<HTMLElement>()
function scrollToEnd(smooth = true) {
  nextTick(() => scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }))
}
watch(() => roundList.value.length, (_n, old) => scrollToEnd(old !== undefined && old > 0))
watch(() => [candidate.value, flow.phase.value], () => scrollToEnd())
onMounted(() => scrollToEnd(false))

// Warn before leaving while a request is running or a candidate would be lost.
function beforeUnload(e: BeforeUnloadEvent) {
  if (['generating', 'archiving'].includes(flow.phase.value) || candidate.value) e.preventDefault()
}
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<template>
  <div class="chat-view" :class="{ 'with-panel': panelOpen }">
    <section class="conversation">
      <TopBar>
        <div class="grow title-wrap">
          <h1 class="ellipsis">{{ chat.data.value?.title ?? '…' }}</h1>
          <div class="faint sub ellipsis" v-if="character && identity">{{ character.name }} · {{ identity.name }}</div>
        </div>
        <span v-if="flow.phase.value === 'incomplete'" class="badge warn">归档未完成</span>
        <span v-else-if="flow.phase.value === 'candidate'" class="badge accent">待确认</span>
        <button class="btn ghost icon" type="button" title="聊天设置" @click="togglePanel('settings')"><Settings2 /></button>
        <button class="btn ghost icon" type="button" :class="{ on: panelOpen }" title="侧边面板" @click="togglePanel()"><PanelRight /></button>
      </TopBar>

      <ErrorBox v-if="chat.error.value" class="m" :error="chat.error.value" title="无法读取聊天" />
      <div ref="scroller" class="timeline">
        <div class="timeline-inner">
          <div v-if="hiddenFloors" class="earlier">
            <button class="btn small" type="button" @click="loadEarlier">
              <ChevronUp /> 加载更早的楼层
            </button>
            <span class="faint">还有 {{ hiddenFloors }} 层未显示</span>
          </div>
          <MessageBubble v-else-if="character" side="ai" page :name="character.name" :avatar="character.avatar" floor="0">
            <template #meta><span v-if="prefs.showFloorNumbers">#0 开场</span></template>
            <OutputView v-if="rawFirstMessage" :text="firstMessage" :raw="raw.has('first')" />
            <p v-else class="faint">（没有开场消息）</p>
            <template #actions>
              <button v-if="rawFirstMessage" class="btn ghost small" type="button" @click="toggle(raw, 'first')"><Code2 /> {{ raw.has('first') ? '渲染' : '原文' }}</button>
            </template>
          </MessageBubble>

          <ErrorBox v-if="rounds.error.value" :error="rounds.error.value" title="无法读取回合" />

          <template v-for="r in shownRounds" :key="r.id">
            <MessageBubble side="user" :name="identity?.name ?? '我'" :avatar="identity?.avatar">
              <template #meta><span v-if="prefs.showFloorNumbers">#{{ r.round_no }}</span></template>
              <div class="plain user-text">{{ r.user_input || '（空输入）' }}</div>
            </MessageBubble>
            <MessageBubble side="ai" page :name="character?.name ?? 'AI'" :avatar="character?.avatar">
              <template #meta>
                <span v-if="prefs.showFloorNumbers">#{{ r.round_no }}</span>
                <span v-if="r.archive_step !== 'complete'" class="badge warn">
                  已保存 · 待{{ STEP_LABELS[r.archive_step] }}
                </span>
              </template>
              <OutputView :text="r.ai_output" :raw="raw.has(r.id)" />
              <template #actions>
                <button class="btn ghost small" type="button" @click="toggle(raw, r.id)"><Code2 /> {{ raw.has(r.id) ? '渲染' : '原文' }}</button>
                <button
                  v-if="r.summary || r.archive_step !== 'state_update'" class="btn ghost small" type="button"
                  :aria-expanded="summaryOpen(r.id)" :aria-controls="`summary-${r.id}`" @click="toggle(openSummaries, r.id)"
                >
                  {{ summaryOpen(r.id) ? '收起摘要' : '摘要' }}
                </button>
              </template>
            </MessageBubble>
            <RoundSummaryBlock
              v-if="summaryOpen(r.id) && (r.summary || r.archive_step !== 'state_update')"
              :id="`summary-${r.id}`" class="indent" :chat-id="chatId" :round-id="r.id" :summary="r.summary"
              :editable="r.id === latest?.id && latestComplete"
            />
            <EpisodeCard
              v-for="ep in episodesByEnd.get(r.id) ?? []" :key="ep.id" class="indent"
              :chat-id="chatId" :episode="ep" :start-no="roundNo.get(ep.start_round_id)" :end-no="roundNo.get(ep.end_round_id)"
              :editable="ep.created_by_round_id === latest?.id && latestComplete"
            />
          </template>

          <!-- Unsaved candidate -->
          <template v-if="candidate">
            <MessageBubble side="user" :name="identity?.name ?? '我'" :avatar="identity?.avatar" pending>
              <template #meta><span class="badge">候选输入</span></template>
              <div class="plain user-text">{{ candidate.user_input || '（空输入）' }}</div>
            </MessageBubble>
            <MessageBubble side="ai" page :name="character?.name ?? 'AI'" :avatar="character?.avatar" pending>
              <template #meta><span class="badge accent">未保存的候选</span></template>
              <OutputView :text="candidate.ai_output" :raw="raw.has('candidate')" />
              <template #actions>
                <button class="btn primary small" type="button" :disabled="flow.phase.value !== 'candidate' || flow.inputChanged.value" @click="flow.confirm()">
                  <Check /> 确认并归档
                </button>
                <button class="btn ghost small" type="button" @click="toggle(raw, 'candidate')"><Code2 /> {{ raw.has('candidate') ? '渲染' : '原文' }}</button>
                <button class="btn ghost small danger" type="button" :disabled="flow.phase.value !== 'candidate'" @click="flow.discardCandidate()"><Trash2 /> 丢弃</button>
              </template>
            </MessageBubble>
            <div v-if="flow.inputChanged.value && flow.phase.value === 'candidate'" class="notice warn indent">
              <AlertTriangle /> 输入框内容与候选的输入不同。请重新生成，使确认的输入与回复保持配对。
            </div>
            <div v-if="candidateProblem" class="notice warn indent"><AlertTriangle /> {{ candidateProblem }}，归档时可能被拒绝。</div>
          </template>

          <MessageBubble v-if="flow.phase.value === 'generating'" side="ai" :name="character?.name ?? 'AI'" :avatar="character?.avatar" pending>
            <div class="row muted"><Loader2 class="spin" /> 正在生成… {{ flow.elapsed.value }}s</div>
          </MessageBubble>
        </div>
      </div>

      <div class="dock">
        <div class="dock-inner stack tight">
          <ArchiveBanner :flow="flow" />
          <ErrorBox v-if="generateError" :error="generateError" title="生成失败">
            <p class="hint">没有产生新的回复，输入内容已保留。</p>
            <p v-if="templateLocation" class="row wrap tpl">
              出错位置：{{ templateLocation }}
              <button class="btn small" type="button" @click="togglePanel('resources')">编辑本聊天的定义</button>
            </p>
          </ErrorBox>
          <div v-if="readiness && chat.data.value" class="notice">
            {{ readiness }}，暂时无法生成。
            <button class="btn small" type="button" @click="togglePanel('settings')">打开聊天设置</button>
          </div>
          <ComposerBar :flow="flow" :can-write="!readiness && !!chat.data.value" :block-reason="readiness" />
        </div>
      </div>
    </section>

    <ChatPanel
      v-if="panelOpen && chat.data.value" class="panel" :chat="chat.data.value" :flow="flow"
      :tab="panelTab" :latest-complete="latestComplete" @update:tab="panelTab = $event" @close="togglePanel()"
    />
  </div>
</template>

<style scoped>
.chat-view { display: flex; height: 100%; }
.conversation { flex: 1; min-width: 0; display: flex; flex-direction: column; height: 100%; }
.title-wrap { min-width: 0; }
.title-wrap h1 { font-size: 16px; }
.sub { font-size: 12px; }
.btn.on { color: var(--accent); }
.m { margin: 12px; }
.timeline { flex: 1; overflow-y: auto; overscroll-behavior: contain; }
.timeline-inner, .dock-inner { max-width: 900px; margin: 0 auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; }
.dock { flex-shrink: 0; background: linear-gradient(to bottom, transparent, var(--bg) 18px); }
.dock-inner { padding-top: 4px; padding-bottom: calc(12px + env(safe-area-inset-bottom)); gap: 8px; }
.indent { margin-left: 44px; }
.user-text { font-size: var(--reading-size); font-family: var(--font-reading); }
.earlier { display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; font-size: 12px; }
.notice { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 12px; border-radius: var(--radius-m); background: var(--warn-soft); font-size: 13px; }
.notice svg { width: 16px; height: 16px; color: var(--warn); flex-shrink: 0; }
.tpl { margin-top: 6px; font-size: 13px; }
.spin { width: 16px; height: 16px; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.panel { width: var(--panel-w); flex-shrink: 0; border-left: 1px solid var(--border); }
.chat-view { position: relative; }
@media (max-width: 1279px) and (min-width: 900px) {
  .panel { position: absolute; top: 0; right: 0; bottom: 0; z-index: 30; width: min(var(--panel-w), 70%); box-shadow: var(--shadow-pop); }
}
@media (max-width: 899px) {
  .panel { position: fixed; inset: 0; z-index: 60; width: auto; border: 0; }
}
@media (max-width: 640px) {
  .indent { margin-left: 0; }
  .timeline-inner { padding: 14px 10px; }
  .dock-inner { padding-left: 8px; padding-right: 8px; }
}
</style>
