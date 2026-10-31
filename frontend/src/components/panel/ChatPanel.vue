<script setup lang="ts">
import { X } from 'lucide-vue-next'
import type { ChatDetail, ChatMemory } from '@/api/endpoints'
import type { RoundFlow } from '@/composables/roundFlow'
import StatePanel from './StatePanel.vue'
import MemoryPanel from './MemoryPanel.vue'
import DefinitionsPanel from './DefinitionsPanel.vue'
import RequestPanel from './RequestPanel.vue'
import ChatSettingsPanel from './ChatSettingsPanel.vue'
import ChatResourcesPanel from './ChatResourcesPanel.vue'

export type PanelTab = 'state' | 'memory' | 'definitions' | 'request' | 'settings' | 'resources'
type Tab = PanelTab
defineProps<{ chat: ChatDetail; flow: RoundFlow; tab: Tab; latestComplete: boolean; memoryTimeline?: ChatMemory | null }>()
const emit = defineEmits<{ 'update:tab': [Tab]; close: [] }>()
const tabs: { id: Tab; label: string }[] = [
  { id: 'state', label: '状态' },
  { id: 'memory', label: '记忆' },
  { id: 'definitions', label: '定义' },
  { id: 'request', label: '请求' },
  { id: 'settings', label: '设置' },
  { id: 'resources', label: '资源' },
]
</script>

<template>
  <aside class="chat-panel">
    <div class="head">
      <nav class="tabs grow">
        <button v-for="t in tabs" :key="t.id" type="button" :class="{ active: tab === t.id }" @click="emit('update:tab', t.id)">{{ t.label }}</button>
      </nav>
      <button class="btn ghost icon" type="button" aria-label="关闭面板" @click="emit('close')"><X /></button>
    </div>
    <div class="content">
      <StatePanel v-if="tab === 'state'" :chat-id="chat.id" :editable="latestComplete && flow.phase.value !== 'archiving'" />
      <MemoryPanel v-else-if="tab === 'memory'" :chat="chat" :timeline="memoryTimeline" :preparing="flow.phase.value === 'preparing' ? flow.prepareLabel : ''" />
      <DefinitionsPanel v-else-if="tab === 'definitions'" :chat="chat" />
      <RequestPanel v-else-if="tab === 'request'" :chat="chat" :flow="flow" />
      <ChatSettingsPanel v-else-if="tab === 'settings'" :chat="chat" />
      <ChatResourcesPanel v-else :chat="chat" />
    </div>
  </aside>
</template>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; background: var(--bg-elev); }
.head { display: flex; align-items: center; gap: 4px; padding: env(safe-area-inset-top) 8px 0 4px; border-bottom: 1px solid var(--border); min-height: var(--topbar-h); }
.head .tabs { border-bottom: 0; }
.head .tabs button { padding: 10px 9px; }
.content { flex: 1; overflow-y: auto; padding: 14px 14px calc(24px + env(safe-area-inset-bottom)); }
</style>
