import { ref } from 'vue'
import { useMediaQuery } from './media'

/** Shared shell state: the sidebar is a drawer below the desktop breakpoint. */
export const sidebarOpen = ref(false)
export const isNarrow = useMediaQuery('(max-width: 899px)')
/** Wide enough for the chat side panel to sit beside the conversation. */
export const isWide = useMediaQuery('(min-width: 1280px)')
