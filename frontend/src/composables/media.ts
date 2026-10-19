import { ref } from 'vue'

export function useMediaQuery(query: string) {
  const mql = window.matchMedia(query)
  const matches = ref(mql.matches)
  mql.addEventListener('change', (e) => (matches.value = e.matches))
  return matches
}
