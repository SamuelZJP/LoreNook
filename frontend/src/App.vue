<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'
import ToastHost from './components/ToastHost.vue'
import { sidebarOpen } from './composables/layout'

const route = useRoute()
watch(() => route.fullPath, () => (sidebarOpen.value = false))
</script>

<template>
  <RouterView v-if="route.meta.bare" />
  <div v-else class="shell" :class="{ 'drawer-open': sidebarOpen }">
    <AppSidebar class="sidebar" />
    <div class="scrim" @click="sidebarOpen = false" />
    <main class="main">
      <RouterView v-slot="{ Component, route: r }">
        <!-- Each chat gets its own view instance so in-flight requests stay tied to their chat. -->
        <component :is="Component" :key="r.name === 'chat' ? r.fullPath : String(r.name)" />
      </RouterView>
    </main>
  </div>
  <ToastHost />
</template>

<style scoped>
/* Floating islands on the wood-toned ground. */
.shell { display: flex; gap: var(--island-gap); height: 100dvh; overflow: hidden; padding: var(--island-gap); background: var(--bg); }
.sidebar { width: var(--sidebar-w); flex-shrink: 0; }
.main {
  flex: 1; min-width: 0; height: 100%; position: relative;
  border-radius: var(--radius-xl); overflow: hidden; background: var(--bg-elev); box-shadow: var(--shadow-island);
}
.scrim { display: none; }
@media (max-width: 899px) {
  .shell { padding: 0; gap: 0; }
  .main { border-radius: 0; box-shadow: none; }
  .sidebar {
    position: fixed; z-index: 50; top: 0; bottom: 0; left: 0; width: min(86vw, 320px); border-radius: 0 var(--radius-xl) var(--radius-xl) 0; overflow: hidden;
    transform: translateX(-100%); transition: transform 0.2s ease; box-shadow: var(--shadow-pop);
  }
  .drawer-open .sidebar { transform: none; }
  .drawer-open .scrim { display: block; position: fixed; inset: 0; z-index: 40; background: rgb(20 14 8 / 45%); }
}
</style>
