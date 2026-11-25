<script setup lang="ts">
import { ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import AvatarBadge from '@/components/AvatarBadge.vue'
import ProfileDialog from './ProfileDialog.vue'
import { currentUser as user } from '../currentUser'

const open = ref(false)
</script>

<template>
  <button class="user-card" type="button" :aria-label="`${user.name}的个人信息`" @click="open = true">
    <AvatarBadge :name="user.name" :src="user.avatar" :size="36" />
    <span class="grow text">
      <span class="name ellipsis">{{ user.name }}</span>
      <span class="handle faint ellipsis">@{{ user.handle }}</span>
    </span>
    <ChevronRight class="chevron" />
  </button>
  <ProfileDialog v-if="open" @close="open = false" />
</template>

<style scoped>
.user-card {
  display: flex; align-items: center; gap: var(--space-3); width: 100%; padding: var(--space-3);
  border: 0; border-radius: inherit; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer;
  transition: background 0.12s;
}
.user-card:hover { background: var(--bg-hover); }
.text { display: flex; flex-direction: column; line-height: 1.35; }
.name { font-weight: 600; }
.handle { font-size: var(--text-xs); }
.chevron { width: 18px; height: 18px; color: var(--text-faint); flex-shrink: 0; }
</style>
