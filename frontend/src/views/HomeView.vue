<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { CheckCircle2, Circle, Plus } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import TopBar from '@/components/TopBar.vue'
import ChatList from '@/components/ChatList.vue'
import { isNarrow, showNewChat } from '@/composables/layout'

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
const health = useQuery({ queryKey: ['health'], queryFn: () => fetch('/health').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))), retry: 0 })

const steps = computed(() => [
  { done: !!characters.data.value?.length, label: '创建角色（含有效的状态 Schema）', to: '/library/characters/new' },
  { done: !!identities.data.value?.length, label: '创建用户身份', to: '/library/identities/new' },
  { done: !!presets.data.value?.length, label: '创建写作预设', to: '/library/presets/new' },
  { done: !!models.data.value?.length, label: '添加模型配置', to: '/library/models/new' },
])
</script>

<template>
  <div class="home">
    <TopBar><h1 class="grow">LoreNook</h1></TopBar>
    <div class="page">
      <div class="page-inner narrow stack">
        <div v-if="health.error.value" class="card card-pad offline">
          <strong>无法连接后端。</strong>请确认 FastAPI 服务正在运行（默认 http://127.0.0.1:8000），并已执行数据库迁移。
        </div>
        <section class="card card-pad stack">
          <h2>开始</h2>
          <p class="muted">准备好资源后即可新建聊天。资源库中的内容会在创建聊天时复制为独立副本。</p>
          <ul class="steps">
            <li v-for="s in steps" :key="s.label">
              <CheckCircle2 v-if="s.done" class="ok" /><Circle v-else class="faint" />
              <RouterLink :to="s.to">{{ s.label }}</RouterLink>
            </li>
          </ul>
          <div><button class="btn primary" type="button" @click="showNewChat = true"><Plus /> 新建聊天</button></div>
        </section>
        <section v-if="isNarrow" class="card card-pad">
          <h2 class="mb">聊天</h2>
          <ChatList />
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home { display: flex; flex-direction: column; height: 100%; }
.home .page { flex: 1; }
.narrow { max-width: 680px; }
.steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.steps li { display: flex; align-items: center; gap: 8px; }
.steps svg { width: 18px; height: 18px; }
.ok { color: var(--ok); }
.offline { background: var(--danger-soft); }
.mb { margin-bottom: 8px; }
</style>
