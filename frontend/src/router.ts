import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from './api/client'
import { account, forgetAccount, isAdmin, loadAccount } from './features/account/session'

declare module 'vue-router' {
  interface RouteMeta {
    /** Open without signing in. */
    public?: boolean
    /** Full-page view without the app's sidebar. */
    bare?: boolean
    admin?: boolean
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: () => import('./views/LandingView.vue'), meta: { public: true, bare: true } },
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true, bare: true } },
    { path: '/hall', name: 'home', component: () => import('./views/HomeView.vue') },
    { path: '/characters/:id', name: 'character', component: () => import('./views/CharacterView.vue'), props: true },
    { path: '/chats/:id', name: 'chat', component: () => import('./views/ChatView.vue'), props: true },
    {
      path: '/library/:tab(characters|identities|presets|models|workflows|templates)?/:id?',
      name: 'library',
      component: () => import('./views/LibraryView.vue'),
    },
    { path: '/data/:scope?/:table?', name: 'data', component: () => import('./views/DataView.vue'), meta: { admin: true } },
    { path: '/settings/:section(appearance|reading|input|advanced)?', name: 'settings', component: () => import('./views/SettingsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

/** Where to go after signing in: the page that asked for it, if it is one of ours. */
export function afterSignIn(redirect: unknown): string {
  return typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/hall'
}

router.beforeEach(async (to) => {
  await loadAccount()
  if (to.meta.public) {
    return to.name === 'login' && account.value ? afterSignIn(to.query.redirect) : true
  }
  if (!account.value) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.admin && !isAdmin.value) return { name: 'home' }
  // Illustrations are for administrators for now.
  if (to.name === 'library' && to.params.tab === 'workflows' && !isAdmin.value) return { name: 'library' }
  return true
})

setUnauthorizedHandler(() => {
  if (!account.value) return
  forgetAccount()
  const here = router.currentRoute.value
  if (!here.meta.public) router.replace({ name: 'login', query: { redirect: here.fullPath } })
})
