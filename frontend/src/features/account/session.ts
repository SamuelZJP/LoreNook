import { computed, ref } from 'vue'
import { ApiError, request, type Schemas } from '@/api/client'
import { queryClient } from '@/lib/queryClient'

/** The signed-in user, from the session cookie; `null` when signed out. */
export type Account = Schemas['AccountRead']

export const account = ref<Account | null>(null)
export const isAdmin = computed(() => account.value?.role === 'admin')

let checked: Promise<void> | null = null

/** Learns who is signed in, once; later calls reuse the answer. */
export function loadAccount(): Promise<void> {
  checked ??= request<Account>('/api/auth/me').then(
    (me) => { account.value = me },
    (error) => {
      account.value = null
      // Only a 401 is an answer; after a network failure ask again next time.
      if (!(error instanceof ApiError && error.status === 401)) checked = null
    },
  )
  return checked
}

export async function signIn(username: string, password: string): Promise<void> {
  queryClient.clear()
  account.value = await request<Account>('/api/auth/login', { method: 'POST', body: { username, password } })
  checked = Promise.resolve()
}

/** Forgets everything cached for the previous user. */
export function forgetAccount() {
  account.value = null
  checked = Promise.resolve()
  queryClient.clear()
}

export async function signOut(): Promise<void> {
  try {
    await request('/api/auth/logout', { method: 'POST' })
  } finally {
    forgetAccount()
  }
}
