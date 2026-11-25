import { isAdmin } from '@/features/account/session'

/** Renders run on the server's own ComfyUI, so only administrators see illustrations for now. */
export const illustrationsAvailable = isAdmin
