<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'
import ToastHost from './components/ToastHost.vue'
import NewChatDialog from './components/NewChatDialog.vue'
import { sidebarOpen, showNewChat } from './composables/layout'

const route = useRoute()
watch(() => route.fullPath, () => (sidebarOpen.value = false))
</script>

<template>
  <div class="shell" :class="{ 'drawer-open': sidebarOpen }">
    <AppSidebar class="sidebar" />
    <div class="scrim" @click="sidebarOpen = false" />
    <main class="main">
      <RouterView v-slot="{ Component, route: r }">
        <!-- Each chat gets its own view instance so in-flight requests stay tied to their chat. -->
        <component :is="Component" :key="r.name === 'chat' ? r.fullPath : String(r.name)" />
      </RouterView>
    </main>
  </div>
  <NewChatDialog v-if="showNewChat" @close="showNewChat = false" />
  <ToastHost />
</template>

<style scoped>
.shell { display: flex; height: 100dvh; overflow: hidden; }
.sidebar { width: var(--sidebar-w); flex-shrink: 0; }
.main { flex: 1; min-width: 0; height: 100%; position: relative; }
.scrim { display: none; }
@media (max-width: 899px) {
  .sidebar {
    position: fixed; z-index: 50; top: 0; bottom: 0; left: 0; width: min(86vw, 320px);
    transform: translateX(-100%); transition: transform 0.2s ease; box-shadow: var(--shadow-pop);
  }
  .drawer-open .sidebar { transform: none; }
  .drawer-open .scrim { display: block; position: fixed; inset: 0; z-index: 40; background: rgb(0 0 0 / 40%); }
}
</style>
