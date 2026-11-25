<script setup lang="ts">
import { ref } from 'vue'
import { Pencil, Plus, KeyRound } from 'lucide-vue-next'
import type { ChatDetail } from '@/api/endpoints'
import ModalDialog from '../ModalDialog.vue'
import AvatarBadge from '../AvatarBadge.vue'
import InfoTip from '../InfoTip.vue'
import ProfileEditor from '../editors/ProfileEditor.vue'
import PresetEditor from '../editors/PresetEditor.vue'
import ModelEditor from '../editors/ModelEditor.vue'
import ChatWorkflowList from '@/features/illustrations/components/ChatWorkflowList.vue'
import { illustrationsAvailable } from '@/features/illustrations/access'

defineProps<{ chat: ChatDetail }>()

type Editing = { kind: 'character' | 'identity' | 'preset' | 'model'; id?: string | null }
const editing = ref<Editing | null>(null)
const titles = { character: '编辑本聊天角色', identity: '编辑本聊天身份', preset: '本聊天的写作风格', model: '本聊天的模型' }
</script>

<template>
  <div class="stack">
    <div class="row">
      <h3>角色与身份</h3>
      <InfoTip>这里的内容属于本聊天，修改不会影响资源库或其他聊天。</InfoTip>
    </div>
    <button class="list-item card" type="button" @click="editing = { kind: 'character' }">
      <AvatarBadge :name="chat.character.name" :src="chat.character.avatar" />
      <div class="grow"><div class="ellipsis"><strong>{{ chat.character.name }}</strong></div><div class="faint">角色 · {{ chat.character.definitions.length }} 条定义</div></div>
      <Pencil class="ic" />
    </button>
    <button class="list-item card" type="button" @click="editing = { kind: 'identity' }">
      <AvatarBadge :name="chat.user_identity.name" :src="chat.user_identity.avatar" />
      <div class="grow"><div class="ellipsis"><strong>{{ chat.user_identity.name }}</strong></div><div class="faint">用户身份 · {{ chat.user_identity.definitions.length }} 条定义</div></div>
      <Pencil class="ic" />
    </button>

    <div class="row"><h3 class="grow">写作风格</h3><button class="btn small" type="button" @click="editing = { kind: 'preset', id: null }"><Plus /> 新增</button></div>
    <div v-if="!chat.writing_presets.length" class="empty">没有写作风格</div>
    <button v-for="p in chat.writing_presets" :key="p.id" class="list-item card" type="button" @click="editing = { kind: 'preset', id: p.id }">
      <div class="grow ellipsis">{{ p.name }}</div>
      <span v-if="p.id === chat.writing_preset_id" class="badge accent">使用中</span>
      <Pencil class="ic" />
    </button>

    <div class="row"><h3 class="grow">模型</h3><button class="btn small" type="button" @click="editing = { kind: 'model', id: null }"><Plus /> 新增</button></div>
    <div v-if="!chat.model_configs.length" class="empty">没有模型</div>
    <button v-for="m in chat.model_configs" :key="m.id" class="list-item card" type="button" @click="editing = { kind: 'model', id: m.id }">
      <div class="grow">
        <div class="ellipsis">{{ m.name }}</div>
        <div class="faint ellipsis mono small">{{ m.api_type }} · {{ m.model }}</div>
      </div>
      <KeyRound v-if="m.has_api_key" class="ic ok" />
      <Pencil class="ic" />
    </button>

    <ChatWorkflowList v-if="illustrationsAvailable" :chat-id="chat.id" />

    <ModalDialog v-if="editing" :title="titles[editing.kind]" width="860px" @close="editing = null">
      <ProfileEditor v-if="editing.kind === 'character' || editing.kind === 'identity'" :kind="editing.kind" :id="null" :chat-id="chat.id" />
      <PresetEditor v-else-if="editing.kind === 'preset'" :id="editing.id ?? null" :chat-id="chat.id" @saved="(id) => (editing = { kind: 'preset', id })" @deleted="editing = null" />
      <ModelEditor v-else :id="editing.id ?? null" :chat-id="chat.id" @saved="(id) => (editing = { kind: 'model', id })" @deleted="editing = null" />
    </ModalDialog>
  </div>
</template>

<style scoped>
.list-item.card { width: 100%; text-align: left; font: inherit; color: inherit; border: 1px solid var(--border); background: var(--bg-elev); }
.ic { width: 16px; height: 16px; color: var(--text-faint); flex-shrink: 0; }
.ic.ok { color: var(--ok); }
.small { font-size: var(--text-xs); }
</style>
