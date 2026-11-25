<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { resolvedTheme } from '@/lib/prefs'
import { reloadAccount } from '@/features/account/session'
import HearthBackdrop from '@/features/home/components/HearthBackdrop.vue'
import HearthTopBar from '@/features/home/components/HearthTopBar.vue'
import WordMark from '@/features/home/components/WordMark.vue'
import { demoApi } from './api'
import '@/features/home/hearth.css'
import '@/features/home/hearthForm.css'

// Redeemed only on the click, so link previews in chat apps cannot start the clock.
const props = defineProps<{ token: string }>()
const router = useRouter()
const night = computed(() => resolvedTheme.value === 'dark')
const error = ref('')
const busy = ref(false)

async function start() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    const { chat_id } = await demoApi.redeem(props.token)
    // A visitor starts from the default layout, not from whatever this browser remembered.
    try { localStorage.removeItem('lorenook.panel') } catch { /* ignore */ }
    await reloadAccount()
    await router.replace(chat_id ? `/chats/${chat_id}` : '/hall')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="hearth hearth-form-page" :class="night ? 'night' : 'day'">
    <HearthBackdrop :night="night" />
    <HearthTopBar />
    <main class="hearth-form-body">
      <WordMark size="compact" tag="h1" />
      <div class="hearth-form">
        <p class="hint">点击下方按钮后开始体验，计时也从这一刻开始。体验期间可以写作、归档和生图；结束后账号与数据会自动清除。</p>
        <p class="error" role="alert">{{ error }}</p>
        <button class="hearth-btn primary submit" type="button" :disabled="busy" @click="start">
          {{ busy ? '正在添柴…' : '欢迎体验' }}
        </button>
      </div>
    </main>
  </div>
</template>
