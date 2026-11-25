import type { ChatSettingsContribution } from '@/components/panel/settings/contract'
import RecallSettingsSection from './components/RecallSettingsSection.vue'
import RecallSummary from './components/RecallSummary.vue'

/** Recall lives inside the chat's memory settings. */
export const recallChatSettings: ChatSettingsContribution = {
  blocks: [{ page: 'memory', order: 10, Block: RecallSettingsSection, Summary: RecallSummary }],
}
