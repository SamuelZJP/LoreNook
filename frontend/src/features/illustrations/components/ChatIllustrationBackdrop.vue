<script setup lang="ts">
import { illustrationApi } from '../api'
import { illustrationPrefs } from '../lib'
import { useChatIllustrations } from '../useChatIllustrations'

/** The latest illustration, blurred. The parent needs `position: relative; isolation: isolate`. */
const c = useChatIllustrations()
</script>

<template>
  <div v-if="c.backdrop.value" class="backdrop" :class="illustrationPrefs.backdrop" aria-hidden="true">
    <img :key="c.backdrop.value.id" :src="illustrationApi.image(c.chatId.value, c.backdrop.value.id)" alt="" />
  </div>
</template>

<style scoped>
.backdrop { position: absolute; inset: 0; overflow: hidden; pointer-events: none; z-index: -1; }
.backdrop img { position: absolute; inset: -80px; width: calc(100% + 160px); height: calc(100% + 160px); object-fit: cover; filter: blur(56px) saturate(1.15); opacity: 0.22; animation: fade-in 1.2s ease; }
.backdrop.strong img { opacity: 0.45; }
.backdrop::after { content: ''; position: absolute; inset: 0; background: color-mix(in srgb, var(--chat-bg, var(--bg)) 35%, transparent); }
@keyframes fade-in { from { opacity: 0; } }
@media (max-width: 640px) { .backdrop { display: none; } }
</style>
