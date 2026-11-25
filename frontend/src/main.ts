import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import { router } from './router'
import './styles/tokens.css'
import '@fontsource-variable/noto-serif-sc'
import './styles/base.css'
import './styles/reading.css'
import './lib/prefs'
import { queryClient } from './lib/queryClient'

const app = createApp(App).use(router).use(VueQueryPlugin, { queryClient })
// Mount once the first route is settled, so nothing asks for data before sign-in is known.
router.isReady().then(() => app.mount('#app'))
