import { createApp } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import App from './App.vue'
import { router } from './router'
import './styles/tokens.css'
import './styles/base.css'
import './lib/prefs'

const queryClient = new QueryClient({
  defaultOptions: {
    // Mutations that call models are never retried automatically.
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 },
    mutations: { retry: false },
  },
})

createApp(App).use(router).use(VueQueryPlugin, { queryClient }).mount('#app')
