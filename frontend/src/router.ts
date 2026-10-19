import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
    { path: '/chats/:id', name: 'chat', component: () => import('./views/ChatView.vue'), props: true },
    {
      path: '/library/:tab(characters|identities|presets|models)?/:id?',
      name: 'library',
      component: () => import('./views/LibraryView.vue'),
    },
    { path: '/data', name: 'data', component: () => import('./views/DataView.vue') },
    { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
