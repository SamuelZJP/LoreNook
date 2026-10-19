<script setup lang="ts">
import { Plus, Library, Database, Settings, Moon, Sun, Monitor } from 'lucide-vue-next'
import ChatList from './ChatList.vue'
import { showNewChat } from '@/composables/layout'
import { prefs } from '@/lib/prefs'

const themes = ['system', 'light', 'dark'] as const
const themeLabel = { system: '跟随系统', light: '浅色', dark: '深色' }
function cycleTheme() {
  prefs.theme = themes[(themes.indexOf(prefs.theme) + 1) % themes.length]
}
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand row">
      <span class="logo">L</span>
      <strong class="grow">LoreNook</strong>
      <button class="btn ghost icon" type="button" :title="`主题：${themeLabel[prefs.theme]}`" @click="cycleTheme">
        <Moon v-if="prefs.theme === 'dark'" /><Sun v-else-if="prefs.theme === 'light'" /><Monitor v-else />
      </button>
    </div>
    <button class="btn primary new" type="button" @click="showNewChat = true"><Plus /> 新建聊天</button>
    <ChatList class="list" />
    <nav class="bottom stack tight">
      <RouterLink to="/library" class="list-item" active-class="active"><Library /> 资源库</RouterLink>
      <RouterLink to="/data" class="list-item" active-class="active"><Database /> 数据管理</RouterLink>
      <RouterLink to="/settings" class="list-item" active-class="active"><Settings /> 设置</RouterLink>
    </nav>
  </aside>
</template>

<style scoped>
.app-sidebar {
  display: flex; flex-direction: column; gap: 10px; height: 100%;
  padding: 12px 10px calc(10px + env(safe-area-inset-bottom)); background: var(--bg-elev); border-right: 1px solid var(--border);
}
.brand { padding: 2px 4px; font-size: 16px; }
.logo { width: 28px; height: 28px; border-radius: 8px; background: var(--accent); color: var(--accent-text); display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
.new { width: 100%; }
.list { flex: 1; overflow-y: auto; min-height: 0; }
.bottom { border-top: 1px solid var(--border); padding-top: 8px; }
.bottom svg { width: 18px; height: 18px; color: var(--text-muted); }
</style>
