import { Image } from 'lucide-vue-next'
import type { ChatSettingsContribution } from '@/components/panel/settings/contract'
import IllustrationSettingsSection from './components/IllustrationSettingsSection.vue'
import IllustrationSummary from './components/IllustrationSummary.vue'
import { illustrationsAvailable } from './access'

export const illustrationChatSettings: ChatSettingsContribution = {
  available: () => illustrationsAvailable.value,
  rows: [{ id: 'illustrations', label: '插图', icon: Image, order: 40, Summary: IllustrationSummary, Page: IllustrationSettingsSection }],
}
