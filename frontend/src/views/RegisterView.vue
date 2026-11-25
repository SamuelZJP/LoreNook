<script setup lang="ts">
import { computed, ref } from 'vue'
import { resolvedTheme } from '@/lib/prefs'
import HearthBackdrop from '@/features/home/components/HearthBackdrop.vue'
import HearthTopBar from '@/features/home/components/HearthTopBar.vue'
import WordMark from '@/features/home/components/WordMark.vue'
import '@/features/home/hearth.css'
import '@/features/home/hearthForm.css'

// Sign-up is not open yet: the form checks what it can, then turns every invite code away.
const night = computed(() => resolvedTheme.value === 'dark')

const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const invite = ref('')
const error = ref('')
const busy = ref(false)

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const filled = computed(() => username.value.trim() && email.value.trim() && password.value && confirm.value && invite.value.trim())

function problem(): string {
  if (!EMAIL.test(email.value.trim())) return '邮箱格式不正确'
  if (password.value.length < 8) return '密码至少 8 位'
  if (password.value !== confirm.value) return '两次输入的密码不一致'
  return ''
}

async function submit() {
  if (busy.value) return
  error.value = problem()
  if (error.value) return
  busy.value = true
  await new Promise((resolve) => setTimeout(resolve, 600))
  error.value = '邀请码无效或已失效'
  invite.value = ''
  busy.value = false
}
</script>

<template>
  <div class="hearth hearth-form-page" :class="night ? 'night' : 'day'">
    <HearthBackdrop :night="night" />
    <HearthTopBar />
    <main class="hearth-form-body">
      <WordMark size="compact" tag="h1" />
      <form class="hearth-form" novalidate @submit.prevent="submit">
        <label class="field">
          <span>用户名</span>
          <input v-model="username" name="username" autocomplete="username" required maxlength="64" autofocus />
        </label>
        <label class="field">
          <span>邮箱</span>
          <input v-model="email" name="email" type="email" autocomplete="email" required maxlength="254" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" name="password" type="password" autocomplete="new-password" required maxlength="256" />
        </label>
        <label class="field">
          <span>确认密码</span>
          <input v-model="confirm" name="confirm" type="password" autocomplete="new-password" required maxlength="256" />
        </label>
        <label class="field">
          <span>邀请码</span>
          <input v-model="invite" name="invite" autocomplete="off" required maxlength="64" spellcheck="false" />
        </label>
        <p class="hint">LoreNook 目前仅向内部成员开放，需持邀请码注册</p>
        <p class="error" role="alert">{{ error }}</p>
        <button class="hearth-btn primary submit" type="submit" :disabled="busy || !filled">
          {{ busy ? '正在核对…' : '领取座位' }}
        </button>
        <p class="aside">已有座位？<RouterLink class="link" to="/login">登录</RouterLink></p>
      </form>
    </main>
  </div>
</template>
