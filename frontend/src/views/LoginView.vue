<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resolvedTheme } from '@/lib/prefs'
import { signIn } from '@/features/account/session'
import { afterSignIn } from '@/router'
import HearthBackdrop from '@/features/home/components/HearthBackdrop.vue'
import HearthTopBar from '@/features/home/components/HearthTopBar.vue'
import WordMark from '@/features/home/components/WordMark.vue'
import '@/features/home/hearth.css'
import '@/features/home/hearthForm.css'

const route = useRoute()
const router = useRouter()
const night = computed(() => resolvedTheme.value === 'dark')

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
  <div class="hearth hearth-form-page" :class="night ? 'night' : 'day'">
    <HearthBackdrop :night="night" />
    <HearthTopBar />
    <main class="hearth-form-body">
      <WordMark size="compact" tag="h1" />
      <form class="hearth-form" @submit.prevent="submit">
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
          还没有座位？<RouterLink class="link" to="/register">注册</RouterLink>
        </p>
      </form>
    </main>
  </div>
</template>

