import { computed } from 'vue'
import { isAdmin, isDemo } from '@/features/account/session'

/** Renders run on the server's own ComfyUI, so only administrators and demo accounts see illustrations for now. */
export const illustrationsAvailable = computed(() => isAdmin.value || isDemo.value)
