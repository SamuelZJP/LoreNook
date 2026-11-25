<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { BookOpen, ChevronDown, Compass, FileJson, Package, ScrollText, Settings2, X } from 'lucide-vue-next'
import type { ChatDetail, ChatMemory } from '@/api/endpoints'
import type { RoundFlow } from '@/composables/roundFlow'
import StatePanel from './StatePanel.vue'
import MemoryPanel from './MemoryPanel.vue'
import DefinitionsPanel from './DefinitionsPanel.vue'
import RequestPanel from './RequestPanel.vue'
import ChatSettingsPanel from './ChatSettingsPanel.vue'
import ChatResourcesPanel from './ChatResourcesPanel.vue'
import DockedIllustration from '@/features/illustrations/components/DockedIllustration.vue'
import { illustrationsAvailable } from '@/features/illustrations/access'

export type PanelTab = 'state' | 'memory' | 'definitions' | 'request' | 'settings' | 'resources'
type Tab = PanelTab
const props = defineProps<{ chat: ChatDetail; flow: RoundFlow; tab: Tab; latestComplete: boolean; memoryTimeline?: ChatMemory | null }>()
const emit = defineEmits<{ 'update:tab': [Tab]; close: [] }>()

// What readers use is up front; what shows how the AI is driven sits in a menu.
const main = [
  { id: 'state' as const, label: '状态', icon: Compass },
  { id: 'memory' as const, label: '记忆', icon: BookOpen },
  { id: 'settings' as const, label: '设置', icon: Settings2 },
]
const behind = [
  { id: 'definitions' as const, label: '设定预览', icon: ScrollText },
  { id: 'request' as const, label: '请求预览', icon: FileJson },
  { id: 'resources' as const, label: '本聊天资源', icon: Package },
]
const behindActive = computed(() => behind.find((b) => b.id === props.tab) ?? null)
// The state editor and raw data take the panel's full height, so the docked illustration steps aside.
const stateRoomy = ref(false)

// A fade at the bottom edge while more content waits below.
const content = ref<HTMLElement>()
const more = ref(false)
function measure() {
  const el = content.value
  more.value = !!el && el.scrollHeight - el.scrollTop - el.clientHeight > 4
}
const sizeObserver = new ResizeObserver(measure)
watch(content, (el, old) => {
  if (old) { sizeObserver.unobserve(old); if (old.firstElementChild) sizeObserver.unobserve(old.firstElementChild) }
  if (el) { sizeObserver.observe(el); if (el.firstElementChild) sizeObserver.observe(el.firstElementChild) }
})
// The tab's own root changes with the tab.
watch(() => props.tab, () => nextTick(() => {
  const el = content.value
  if (!el) return
  sizeObserver.disconnect()
  sizeObserver.observe(el)
  if (el.firstElementChild) sizeObserver.observe(el.firstElementChild)
  measure()
}))
onBeforeUnmount(() => sizeObserver.disconnect())

const menuOpen = ref(false)
const menu = ref<HTMLElement>()
function outside(e: Event) {
  if (!menu.value?.contains(e.target as Node)) menuOpen.value = false
}
watch(menuOpen, (open) => {
  if (open) document.addEventListener('pointerdown', outside, true)
  else document.removeEventListener('pointerdown', outside, true)
})
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside, true))
function pick(id: Tab) {
  menuOpen.value = false
  emit('update:tab', id)
}
</script>

<template>
  <aside class="chat-panel">
    <div class="head">
      <nav class="icon-tabs grow">
        <button v-for="t in main" :key="t.id" type="button" :class="{ active: tab === t.id }" @click="emit('update:tab', t.id)">
          <component :is="t.icon" /><span>{{ t.label }}</span>
        </button>
        <div ref="menu" class="behind">
          <button type="button" :class="{ active: !!behindActive }" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">
            <component :is="behindActive?.icon ?? Package" /><span>{{ behindActive?.label ?? '幕后' }}</span><ChevronDown class="caret" />
          </button>
          <div v-if="menuOpen" class="menu" role="menu">
            <button v-for="b in behind" :key="b.id" type="button" role="menuitem" :class="{ active: tab === b.id }" @click="pick(b.id)">
              <component :is="b.icon" /> {{ b.label }}
            </button>
          </div>
        </div>
      </nav>
      <button class="btn ghost icon" type="button" aria-label="关闭面板" @click="emit('close')"><X /></button>
    </div>
    <div ref="content" class="content" :class="{ more }" @scroll.passive="measure">
      <StatePanel
        v-if="tab === 'state'" :chat-id="chat.id" :editable="latestComplete && flow.phase.value !== 'archiving'"
        @roomy="stateRoomy = $event"
      />
      <MemoryPanel v-else-if="tab === 'memory'" :chat="chat" :timeline="memoryTimeline" :preparing="flow.phase.value === 'preparing' ? flow.prepareLabel : ''" />
      <DefinitionsPanel v-else-if="tab === 'definitions'" :chat="chat" />
      <RequestPanel v-else-if="tab === 'request'" :chat="chat" :flow="flow" />
      <ChatSettingsPanel v-else-if="tab === 'settings'" :chat="chat" />
      <ChatResourcesPanel v-else :chat="chat" />
    </div>
    <DockedIllustration v-if="illustrationsAvailable && tab === 'state' && !stateRoomy" class="illustration" />
  </aside>
</template>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; background: var(--bg-elev); }
.head { display: flex; align-items: center; gap: var(--space-1); padding: calc(env(safe-area-inset-top) + var(--space-3)) var(--space-2) 0 var(--space-3); }
/* A segmented control: the reader's tabs, then the behind-the-scenes menu. */
.icon-tabs { display: flex; align-items: center; gap: var(--space-0-5); min-width: 0; padding: var(--space-1); border-radius: var(--radius-m); background: var(--bg-sunken); }
.icon-tabs button, .menu button {
  display: inline-flex; align-items: center; gap: var(--space-1); border: 0; background: none; font: inherit; cursor: pointer;
  color: var(--text-muted); font-weight: 500; font-size: var(--text-sm); white-space: nowrap;
}
.icon-tabs > button, .behind > button { justify-content: center; min-height: 32px; padding: 0 var(--space-2); border-radius: var(--radius-s); }
.icon-tabs > button { flex: 1; }
.behind { position: relative; flex: 1; display: flex; }
.behind > button { flex: 1; }
.icon-tabs > button:hover, .behind > button:hover { color: var(--text); }
.icon-tabs button.active { color: var(--text); background: var(--bg-elev); box-shadow: 0 1px 3px rgb(0 0 0 / 8%); }
.icon-tabs svg, .menu svg { width: 15px; height: 15px; flex-shrink: 0; }
.icon-tabs .caret { width: 13px; height: 13px; }
.menu {
  position: absolute; right: 0; top: calc(100% + 8px); z-index: 20; min-width: 160px; padding: var(--space-1);
  display: flex; flex-direction: column; border-radius: var(--radius-m); background: var(--bg-elev);
  border: 1px solid var(--border); box-shadow: var(--shadow-pop);
}
.menu button { width: 100%; padding: var(--space-2) var(--space-3); border-radius: var(--radius-s); color: var(--text); }
.menu button:hover { background: var(--bg-hover); }
.menu button.active { background: var(--bg-active); }
@media (max-width: 899px) {
  /* Grabber of the bottom sheet */
  .head { position: relative; padding-top: var(--space-5); }
  .head::before { content: ''; position: absolute; top: var(--space-1-5); left: 50%; width: 36px; height: 4px; margin-left: -18px; border-radius: var(--radius-pill); background: var(--border-strong); }
}
.content.more { mask-image: linear-gradient(to bottom, #000 calc(100% - 48px), transparent); }
.content { flex: 1; min-height: 0; overflow-y: auto; padding: var(--space-5) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom)); }
</style>
