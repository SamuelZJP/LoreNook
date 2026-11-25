<script setup lang="ts">
import ModalDialog from '@/components/ModalDialog.vue'
import AvatarBadge from '@/components/AvatarBadge.vue'
import { currentUser as user } from '../currentUser'

const emit = defineEmits<{ close: [] }>()

const rows = [
  { label: '用户名', value: user.handle },
  { label: '邮箱', value: user.email },
  { label: '注册时间', value: user.joinedAt },
]
</script>

<template>
  <ModalDialog title="个人信息" width="420px" @close="emit('close')">
    <div class="head">
      <AvatarBadge :name="user.name" :src="user.avatar" :size="64" />
      <div class="grow">
        <div class="name ellipsis">{{ user.name }}</div>
        <div class="handle faint ellipsis">@{{ user.handle }}</div>
      </div>
    </div>
    <dl class="info">
      <template v-for="row in rows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd class="ellipsis">{{ row.value }}</dd>
      </template>
    </dl>
    <template #footer>
      <button class="btn danger" type="button">退出登录</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: var(--space-4); padding-bottom: var(--space-4); }
.name { font-family: var(--font-reading); font-size: var(--text-xl); font-weight: 600; }
.handle { font-size: var(--text-sm); }
.info {
  display: grid; grid-template-columns: auto 1fr; gap: var(--space-3) var(--space-4); margin: 0;
  padding-top: var(--space-4); border-top: 1px solid var(--border);
}
dt { color: var(--text-muted); font-size: var(--text-sm); }
dd { margin: 0; min-width: 0; }
</style>
