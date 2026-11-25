<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resolvedTheme } from '@/lib/prefs'
import { signIn } from '@/features/account/session'
import { afterSignIn } from '@/router'
import HearthBackdrop from '@/features/home/components/HearthBackdrop.vue'
import HearthTopBar from '@/features/home/components/HearthTopBar.vue'
import WordMark from '@/features/home/components/WordMark.vue'
import { REGISTRATION_CLOSED, useNote } from '@/features/home/useNote'
import '@/features/home/hearth.css'

const route = useRoute()
const router = useRouter()
const night = computed(() => resolvedTheme.value === 'dark')
const { note, show } = useNote()

const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    await signIn(username.value.trim(), password.value)
    await router.replace(afterSignIn(route.query.redirect))
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="hearth login" :class="night ? 'night' : 'day'">
    <HearthBackdrop :night="night" />
    <HearthTopBar />
    <main class="body">
      <WordMark size="compact" tag="h1" />
      <form class="form" @submit.prevent="submit">
        <label class="field">
          <span>用户名</span>
          <input v-model="username" name="username" autocomplete="username" required maxlength="64" autofocus />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" name="password" type="password" autocomplete="current-password" required maxlength="256" />
        </label>
        <p class="error" role="alert">{{ error }}</p>
        <button class="hearth-btn primary submit" type="submit" :disabled="busy || !username.trim() || !password">
          {{ busy ? '正在添柴…' : '进入炉边' }}
        </button>
        <p class="aside">
          还没有座位？<button class="link" type="button" @click="show(REGISTRATION_CLOSED)">注册</button>
        </p>
      </form>
    </main>
    <div v-if="note" class="hearth-note" role="status">{{ note }}</div>
  </div>
</template>

<style scoped>
.login { height: 100dvh; overflow-y: auto; }
.body {
  position: relative; min-height: 100dvh; box-sizing: border-box; padding: 120px 24px 80px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 56px;
}
.form { width: min(340px, 100%); display: flex; flex-direction: column; gap: 22px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field span { font-family: var(--h-sans); font-size: 12px; letter-spacing: 0.3em; color: var(--h-muted); }
.field input {
  width: 100%; box-sizing: border-box; padding: 10px 2px; border: 0; border-bottom: 1px solid var(--h-line); border-radius: 0;
  background: transparent; color: var(--h-ink); font-family: var(--h-serif); font-size: 17px; letter-spacing: 0.06em;
  transition: border-color 0.3s ease;
}
.field input:focus { outline: none; border-bottom-color: var(--h-accent); }
.error { min-height: 1.6em; margin: -6px 0 0; font-family: var(--h-sans); font-size: 13px; letter-spacing: 0.06em; color: var(--h-accent); }
.submit { width: 100%; }
.aside { margin: 0; text-align: center; font-family: var(--h-sans); font-size: 13px; letter-spacing: 0.14em; color: var(--h-muted); }
.link {
  padding: 4px 2px; border: 0; background: none; color: var(--h-ink); font: inherit; letter-spacing: inherit; cursor: pointer;
  text-decoration: underline; text-decoration-color: var(--h-line); text-underline-offset: 4px;
}
.link:hover { text-decoration-color: var(--h-ink); }
</style>
