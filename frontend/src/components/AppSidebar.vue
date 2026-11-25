<script setup lang="ts">
import { Plus, Library, Settings, Moon, Sun, Monitor } from 'lucide-vue-next'
import ChatList from './ChatList.vue'
import UserCard from '@/features/account/components/UserCard.vue'
import { prefs } from '@/lib/prefs'

const themes = ['system', 'light', 'dark'] as const
const themeLabel = { system: '跟随系统', light: '浅色', dark: '深色' }
function cycleTheme() {
  prefs.theme = themes[(themes.indexOf(prefs.theme) + 1) % themes.length]
}
</script>

<template>
  <aside class="app-sidebar">
    <div class="panel">
      <div class="brand row">
        <span class="logo">L</span>
        <strong class="grow">LoreNook</strong>
        <button class="btn ghost icon" type="button" :title="`主题：${themeLabel[prefs.theme]}`" @click="cycleTheme">
          <Moon v-if="prefs.theme === 'dark'" /><Sun v-else-if="prefs.theme === 'light'" /><Monitor v-else />
        </button>
      </div>
      <RouterLink to="/" class="btn primary new"><Plus /> 新建聊天</RouterLink>
      <ChatList class="list" />
      <nav class="bottom stack tight">
        <RouterLink to="/library" class="list-item" active-class="active"><Library /> 资源库</RouterLink>
        <RouterLink to="/settings" class="list-item" active-class="active" :class="{ active: $route.path.startsWith('/data') }"><Settings /> 设置</RouterLink>
      </nav>
    </div>
    <div class="account"><UserCard /></div>
  </aside>
</template>

<style scoped>
/* Two islands: navigation, then the signed-in user. */
.app-sidebar { display: flex; flex-direction: column; gap: var(--island-gap); height: 100%; }
.panel, .account { background: var(--bg-elev); border-radius: var(--radius-xl); box-shadow: var(--shadow-island); overflow: hidden; }
.panel { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-4) var(--space-3) var(--space-3); }
.account { flex-shrink: 0; padding-bottom: env(safe-area-inset-bottom); }
.brand { padding: 0 var(--space-1) 0 var(--space-1-5); font-size: var(--text-xl); font-family: var(--font-reading); letter-spacing: 0.01em; }
.brand strong { font-weight: 700; }
.logo { width: 30px; height: 30px; border-radius: 9px; background: var(--accent); color: var(--accent-text); display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-reading); font-weight: 600; font-size: var(--text-lg); }
.new { width: 100%; min-height: 42px; font-weight: 600; }
.list { flex: 1; overflow-y: auto; min-height: 0; }
.bottom { border-top: 1px solid var(--border); padding-top: var(--space-2); }
.bottom .list-item { padding: var(--space-2) var(--space-3); font-weight: 500; }
.bottom svg { width: 18px; height: 18px; color: var(--text-muted); }
@media (max-width: 899px) {
  /* In the drawer the outer shape is the drawer's; a ground-coloured band separates the islands. */
  .app-sidebar { background: var(--bg); }
  .panel, .account { border-radius: 0; box-shadow: none; }
}
</style>
