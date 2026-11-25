import { onScopeDispose, ref } from 'vue'
import { homeApi } from './api'

/** The fireside count and ICP number for the public pages; refreshed every minute while shown. */
export function useHomeInfo() {
  const online = ref<number | null>(null)
  const icp = ref('')
  async function load() {
    try {
      const info = await homeApi.info()
      online.value = info.online
      icp.value = info.icp_number
    } catch {
      // Decorative: keep the last number.
    }
  }
  load()
  const timer = setInterval(load, 60_000)
  onScopeDispose(() => clearInterval(timer))
  return { online, icp }
}
