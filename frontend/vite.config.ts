import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backend = process.env.LORENOOK_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // Editable examples shipped with the backend, imported as raw text.
      '@examples': fileURLToPath(new URL('../backend/modules', import.meta.url)),
    },
  },
  server: {
    fs: { allow: ['..'] },
    proxy: {
      // Generation and archiving can take minutes; never let the proxy cut them off.
      '/api': { target: backend, timeout: 0, proxyTimeout: 0 },
      '/health': { target: backend },
    },
  },
})
