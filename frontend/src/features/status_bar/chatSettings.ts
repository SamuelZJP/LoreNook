import { PanelBottom } from 'lucide-vue-next'
import type { ChatSettingsContribution } from '@/components/panel/settings/contract'
import StatusBarSettingsSection from './components/StatusBarSettingsSection.vue'

/** A switch right on its row; no page of its own. */
export const statusBarChatSettings: ChatSettingsContribution = {
  rows: [{ id: 'status-bar', label: '状态栏', icon: PanelBottom, order: 50, Summary: StatusBarSettingsSection }],
}
