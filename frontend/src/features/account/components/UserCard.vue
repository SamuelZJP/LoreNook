<script setup lang="ts">
import { ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import AvatarBadge from '@/components/AvatarBadge.vue'
import ProfileDialog from './ProfileDialog.vue'
import { account } from '../session'

const open = ref(false)
</script>

<template>
  <button v-if="account" class="user-card" type="button" :aria-label="`${account.username}的个人信息`" @click="open = true">
    <AvatarBadge :name="account.username" :size="36" />
    <span class="grow text">
      <span class="name ellipsis">{{ account.username }}</span>
      <span class="handle faint ellipsis">{{ account.role === 'admin' ? '管理员' : '炉友' }}</span>
    </span>
    <ChevronRight class="chevron" />
  </button>
  <ProfileDialog v-if="open && account" :account="account" @close="open = false" />
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
