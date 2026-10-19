import type { RoundRead, PendingStep } from '@/api/endpoints'

export const STEP_LABELS: Record<RoundRead['archive_step'], string> = {
  state_update: '状态更新',
  round_summary: '回合摘要',
  episode_decision: '情节判定',
  episode_summary: '情节摘要',
  complete: '已完成',
}

export const STEP_ORDER: RoundRead['archive_step'][] = [
  'state_update',
  'round_summary',
  'episode_decision',
  'episode_summary',
  'complete',
]

export const PURPOSE_LABELS = {
  writing: '写作',
  state_update: '状态更新',
  round_summary: '回合摘要',
  episode_summary: '情节摘要',
} as const

export function pendingStep(round: RoundRead | null | undefined): PendingStep | null {
  if (!round || round.archive_step === 'complete') return null
  return round.archive_step
}
