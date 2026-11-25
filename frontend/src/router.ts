import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
    { path: '/characters/:id', name: 'character', component: () => import('./views/CharacterView.vue'), props: true },
    { path: '/chats/:id', name: 'chat', component: () => import('./views/ChatView.vue'), props: true },
    {
      path: '/library/:tab(characters|identities|presets|models|workflows|templates)?/:id?',
      name: 'library',
      component: () => import('./views/LibraryView.vue'),
    },
    { path: '/data/:scope?/:table?', name: 'data', component: () => import('./views/DataView.vue') },
    { path: '/settings/:section(appearance|reading|input|advanced)?', name: 'settings', component: () => import('./views/SettingsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
