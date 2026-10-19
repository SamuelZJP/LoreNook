<script setup lang="ts">
import { computed } from 'vue'
import { Check, Loader2, AlertCircle, Circle, RotateCw, RefreshCw } from 'lucide-vue-next'
import type { RoundFlow } from '@/composables/roundFlow'
import { STEP_LABELS, STEP_ORDER } from '@/lib/archive'
import ErrorBox from '../ErrorBox.vue'

const props = defineProps<{ flow: RoundFlow }>()
const round = computed(() => props.flow.latestRound.value)
const phase = computed(() => props.flow.phase.value)
const err = computed(() => props.flow.error.value)
const showErr = computed(() => err.value && ['confirm', 'retry', 'check'].includes(err.value.action))

const steps = computed(() => {
  const r = round.value
  if (!r) return []
  const current = STEP_ORDER.indexOf(r.archive_step)
  const includeEpisode = r.episode_required !== false || r.archive_step === 'episode_summary'
  return STEP_ORDER.filter((s) => s !== 'complete' && (s !== 'episode_summary' || includeEpisode)).map((s) => {
    const i = STEP_ORDER.indexOf(s)
    let status: 'done' | 'current' | 'todo' = i < current ? 'done' : i === current ? 'current' : 'todo'
    if (r.archive_step === 'complete') status = 'done'
    return { step: s, label: STEP_LABELS[s], status }
  })
})
const visible = computed(() => phase.value === 'archiving' || phase.value === 'incomplete' || phase.value === 'checking' || showErr.value)
</script>

<template>
  <div v-if="visible" class="banner" :class="{ failed: phase === 'incomplete' && round?.archive_error }">
    <div class="row wrap head">
      <strong v-if="phase === 'archiving'">正在归档第 {{ round?.round_no ?? '' }} 回合 · {{ flow.elapsed.value }}s</strong>
      <strong v-else-if="phase === 'checking'">正在读取归档进度…</strong>
      <strong v-else-if="phase === 'incomplete'">第 {{ round?.round_no }} 回合已保存，归档未完成</strong>
      <strong v-else>归档提示</strong>
      <span class="spacer" />
      <button v-if="phase === 'incomplete'" class="btn small" type="button" @click="flow.checkProgress()"><RefreshCw /> 刷新进度</button>
      <button v-if="phase === 'incomplete'" class="btn primary small" type="button" @click="flow.retry()">
        <RotateCw /> 继续归档：{{ STEP_LABELS[round!.archive_step] }}
      </button>
    </div>
    <ol v-if="round && phase !== 'checking'" class="steps">
      <li class="done"><Check /> 保存文本</li>
      <li v-for="s in steps" :key="s.step" :class="s.status">
        <Check v-if="s.status === 'done'" />
        <Loader2 v-else-if="s.status === 'current' && phase === 'archiving'" class="spin" />
        <AlertCircle v-else-if="s.status === 'current'" />
        <Circle v-else />
        {{ s.label }}
      </li>
    </ol>
    <p v-if="phase === 'incomplete' && round?.archive_error" class="saved-error">
      <strong>记录的错误：</strong>{{ round.archive_error }}
    </p>
    <p v-else-if="phase === 'incomplete'" class="hint">
      该步骤没有错误记录，可能是请求中断。继续归档只会从当前步骤开始，不会重复已完成的步骤。
    </p>
    <ErrorBox v-if="showErr && err" :error="err.error" :title="err.action === 'retry' ? '继续归档失败' : err.action === 'check' ? '读取进度失败' : '确认失败'">
      <p v-if="err.note" class="note">{{ err.note }}</p>
    </ErrorBox>
  </div>
</template>

<style scoped>
.banner { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border-radius: var(--radius-m); background: var(--info-soft); border: 1px solid var(--border); }
.banner.failed { background: var(--warn-soft); }
.steps { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 0; padding: 0; list-style: none; font-size: 13px; }
.steps li { display: inline-flex; align-items: center; gap: 4px; color: var(--text-faint); }
.steps li.done { color: var(--ok); }
.steps li.current { color: var(--warn); font-weight: 600; }
.steps svg { width: 14px; height: 14px; }
.saved-error { font-size: 13px; white-space: pre-wrap; word-break: break-word; }
.note { margin-top: 6px; font-size: 13px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
