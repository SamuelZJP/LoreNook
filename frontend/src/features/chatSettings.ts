import type { ChatSettingsContribution } from '@/components/panel/settings/contract'
import { illustrationChatSettings } from './illustrations/chatSettings'
import { recallChatSettings } from './recall/chatSettings'
import { statusBarChatSettings } from './status_bar/chatSettings'

/** What the installed features add to a chat's settings. */
export const CHAT_SETTINGS: ChatSettingsContribution[] = [recallChatSettings, illustrationChatSettings, statusBarChatSettings]
