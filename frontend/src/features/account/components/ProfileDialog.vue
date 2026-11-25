<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ModalDialog from '@/components/ModalDialog.vue'
import AvatarBadge from '@/components/AvatarBadge.vue'
import { toast } from '@/composables/toast'
import { signOut, type Account } from '../session'

const props = defineProps<{ account: Account }>()
const emit = defineEmits<{ close: [] }>()
const router = useRouter()
const leaving = ref(false)

const rows = [
  { label: '用户名', value: props.account.username },
  { label: '身份', value: props.account.role === 'admin' ? '管理员' : '炉友' },
]

async function leave() {
  leaving.value = true
  try {
    await signOut()
    await router.push('/')
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    leaving.value = false
  }
}
</script>

<template>
  <ModalDialog title="个人信息" width="420px" @close="emit('close')">
    <div class="head">
      <AvatarBadge :name="account.username" :size="64" />
      <div class="grow">
        <div class="name ellipsis">{{ account.username }}</div>
      </div>
    </div>
    <dl class="info">
      <template v-for="row in rows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd class="ellipsis">{{ row.value }}</dd>
      </template>
    </dl>
    <template #footer>
      <button class="btn danger" type="button" :disabled="leaving" @click="leave">退出登录</button>
    </template>
  </ModalDialog>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: var(--space-4); padding-bottom: var(--space-4); }
.name { font-family: var(--font-reading); font-size: var(--text-xl); font-weight: 600; }
.info {
  display: grid; grid-template-columns: auto 1fr; gap: var(--space-3) var(--space-4); margin: 0;
  padding-top: var(--space-4); border-top: 1px solid var(--border);
}
dt { color: var(--text-muted); font-size: var(--text-sm); }
dd { margin: 0; min-width: 0; }
</style>
