<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronRight, Database, Plus, RotateCcw, Trash2 } from 'lucide-vue-next'
import TopBar from '@/components/TopBar.vue'
import InfoTip from '@/components/InfoTip.vue'
import Segmented from '@/components/Segmented.vue'
import OutputView from '@/components/chat/OutputView.vue'
import { categoryDefaultMode, prefs, resetPrefs, REPLY_CAP_RANGE, type RenderCategory, type SectionMode } from '@/lib/prefs'
import { EN_FONTS, ZH_FONTS } from '@/lib/fonts'
import BackdropPreference from '@/features/illustrations/components/BackdropPreference.vue'

type Section = 'appearance' | 'reading' | 'input' | 'advanced'
const SECTIONS: { id: Section; label: string }[] = [
  { id: 'appearance', label: '外观' },
  { id: 'reading', label: '阅读' },
  { id: 'input', label: '输入' },
  { id: 'advanced', label: '高级' },
]
const route = useRoute()
const section = computed<Section>(() => (route.params.section as Section) || 'appearance')

const themes = [
  { value: 'system' as const, label: '跟随系统' },
  { value: 'light' as const, label: '浅色' },
  { value: 'dark' as const, label: '深色' },
]
const sendKeys = [
  { value: 'ctrl-enter' as const, label: 'Ctrl/⌘ + Enter' },
  { value: 'enter' as const, label: 'Enter' },
]

// Floor limit: a few common choices, plus whatever number is already stored.
const FLOOR_CHOICES = [50, 100, 200, 500]
const floorOptions = computed(() => {
  const values: (number | null)[] = [...FLOOR_CHOICES]
  if (prefs.floorLimit !== null && !FLOOR_CHOICES.includes(prefs.floorLimit)) values.push(prefs.floorLimit)
  return [...values.sort((a, b) => a! - b!).map((v) => ({ value: v, label: `${v} 层` })), { value: null, label: '全部' }]
})
const floorLimit = computed({ get: () => prefs.floorLimit, set: (v) => (prefs.floorLimit = v) })

// Reply height limit: a switch and a slider; the slider keeps its value while the switch is off.
const capValue = ref(prefs.replyCap ?? 100)
const capOn = computed({
  get: () => prefs.replyCap !== null,
  set: (on) => (prefs.replyCap = on ? capValue.value : null),
})
function setCap(v: number) {
  capValue.value = v
  if (prefs.replyCap !== null) prefs.replyCap = v
}

// Output tag rules
const modes: { id: SectionMode; label: string }[] = [
  { id: 'show', label: '显示' },
  { id: 'collapse', label: '折叠' },
  { id: 'hide', label: '隐藏' },
]
const categories: { id: RenderCategory; label: string }[] = [
  { id: 'prose', label: '正文' },
  { id: 'thought', label: '思维链' },
  { id: 'other', label: '其他' },
]
const newTag = ref('')
const newCategory = ref<RenderCategory | ''>('')
const newTagName = computed(() => newTag.value.trim().replace(/^<\/?|>$/g, ''))
const addProblem = computed(() => {
  if (!newTagName.value) return null
  if (!/^[A-Za-z_][\w\-~.:]*$/.test(newTagName.value)) return '标签名需以字母或下划线开头，只含字母、数字和 _ - ~ . :'
  if (newTagName.value in prefs.sections) return '这个标签已在列表中'
  return null
})
function addTag() {
  const category = newCategory.value
  if (!newTagName.value || !category || addProblem.value) return
  prefs.sections[newTagName.value] = { category, mode: categoryDefaultMode[category] }
  newTag.value = ''
  newCategory.value = ''
}
function removeTag(name: string) {
  delete prefs.sections[name]
}

function reset() {
  if (confirm('恢复所有界面偏好为默认值？')) {
    resetPrefs()
    capValue.value = prefs.replyCap ?? 100
  }
}

const fontSample = `窗外的雨停了。她翻开那本 The Little Prince（1943 年初版），轻声念道："All grown-ups were once children." 然后合上书，说："我们走吧。"`
const sample = `<think>她还不确定该不该提起那封信，也许先试探一下。</think>
<content>凌晨 3:40，雨势小了些。她把那本 1998 年版的《Le Petit Prince》合上，轻声说了句“随便你吧”。
“走吧。”她站起身，把伞递给你。</content>
<status>好感度 62 → 63 · 第 3 天 21:40</status>`
</script>

<template>
  <div class="settings">
    <TopBar class="narrow-only"><strong class="grow">设置</strong></TopBar>
    <div class="page">
      <div class="inner stack">
        <h1 class="display">设置</h1>
        <nav class="section-nav">
          <RouterLink v-for="s in SECTIONS" :key="s.id" :to="`/settings/${s.id}`" :class="{ on: section === s.id }">{{ s.label }}</RouterLink>
        </nav>

        <!-- Appearance -->
        <template v-if="section === 'appearance'">
          <section class="card rows">
            <div class="setting">
              <span class="name">主题</span>
              <Segmented v-model="prefs.theme" :options="themes" label="主题" />
            </div>
            <div class="setting">
              <span class="name">正文字号</span>
              <div class="row range-row">
                <input v-model.number="prefs.fontSize" type="range" min="13" max="22" step="1" aria-label="正文字号" />
                <span class="value">{{ prefs.fontSize }}px</span>
              </div>
            </div>
            <div class="setting">
              <span class="name">中文字体 <InfoTip>缺少的字体会自动改用相近字体。思源宋体随应用加载。</InfoTip></span>
              <select v-model="prefs.zhFont" class="select narrow" aria-label="中文字体">
                <option v-for="f in ZH_FONTS" :key="f.id" :value="f.id">{{ f.label }}</option>
              </select>
            </div>
            <div class="setting">
              <span class="name">英文字体</span>
              <select v-model="prefs.enFont" class="select narrow" aria-label="英文字体">
                <option v-for="f in EN_FONTS" :key="f.id" :value="f.id">{{ f.label }}</option>
              </select>
            </div>
            <div class="card card-pad page-surface font-preview">
              <p class="reading-prose">{{ fontSample }}</p>
              <p class="summary-sample">回合摘要：她在雨夜读完 The Little Prince，决定和你一起离开书店。</p>
            </div>
          </section>
          <BackdropPreference />
        </template>

        <!-- Reading -->
        <section v-else-if="section === 'reading'" class="card rows">
          <label class="setting">
            <span class="name">Markdown 排版</span>
            <input v-model="prefs.markdown" type="checkbox" class="switch" />
          </label>
          <label class="setting">
            <span class="name">显示楼层编号</span>
            <input v-model="prefs.showFloorNumbers" type="checkbox" class="switch" />
          </label>
          <label class="setting">
            <span class="name">默认展开回合摘要</span>
            <input v-model="prefs.showSummaries" type="checkbox" class="switch" />
          </label>
          <div class="setting">
            <span class="name">一次显示的楼层 <InfoTip>更早的楼层可在聊天顶部加载。不影响 AI 能看到的内容。</InfoTip></span>
            <Segmented v-model="floorLimit" :options="floorOptions" label="一次显示的楼层" />
          </div>
          <label class="setting">
            <span class="name">限制回复框高度 <InfoTip>太长的回复在框内滚动，插图和状态栏保持可见。</InfoTip></span>
            <input v-model="capOn" type="checkbox" class="switch" />
          </label>
          <div v-if="capOn" class="setting sub">
            <span class="name muted">最高为聊天区的</span>
            <div class="row range-row">
              <input
                type="range" :min="REPLY_CAP_RANGE.min" :max="REPLY_CAP_RANGE.max" step="10" :value="capValue"
                aria-label="回复框高度上限" @input="setCap(Number(($event.target as HTMLInputElement).value))"
              />
              <span class="value">{{ capValue }}%</span>
            </div>
          </div>
        </section>

        <!-- Input -->
        <section v-else-if="section === 'input'" class="card rows">
          <div class="setting">
            <span class="name">发送 <InfoTip v-if="prefs.sendKey === 'enter'">Shift + Enter 换行。</InfoTip></span>
            <Segmented v-model="prefs.sendKey" :options="sendKeys" label="发送快捷键" />
          </div>
        </section>

        <!-- Advanced -->
        <template v-else>
          <section class="card card-pad stack">
            <div class="row">
              <h2>输出标签</h2>
              <InfoTip>
                AI 输出按顶层标签分段显示，只影响显示，保存的始终是原文。
                正文用书页排版，思维链是可展开的批注，其他是紧凑的附注。
              </InfoTip>
            </div>
            <div class="tag-table">
              <div v-for="(rule, name) in prefs.sections" :key="name" class="tag-row">
                <code class="grow">&lt;{{ name }}&gt;</code>
                <select v-model="rule.category" class="select cat" :aria-label="`${name} 的渲染类别`">
                  <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.label }}</option>
                </select>
                <select v-model="rule.mode" class="select mode" :aria-label="`${name} 的显示方式`">
                  <option v-for="m in modes" :key="m.id" :value="m.id">{{ m.label }}</option>
                </select>
                <button class="btn ghost icon small" type="button" :title="`移除 ${name}`" @click="removeTag(String(name))"><Trash2 /></button>
              </div>
              <div v-for="row in [{ rule: prefs.unknownSection, label: '其他标签' }, { rule: prefs.looseText, label: '标签外的文字' }]" :key="row.label" class="tag-row">
                <span class="grow muted">{{ row.label }}</span>
                <select v-model="row.rule.category" class="select cat" :aria-label="`${row.label}的渲染类别`">
                  <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.label }}</option>
                </select>
                <select v-model="row.rule.mode" class="select mode" :aria-label="`${row.label}的显示方式`">
                  <option v-for="m in modes" :key="m.id" :value="m.id">{{ m.label }}</option>
                </select>
                <span class="btn-spacer" />
              </div>
            </div>
            <div class="row wrap add-row">
              <input v-model="newTag" class="input grow" placeholder="report_nya~" aria-label="新标签名" @keydown.enter="addTag" />
              <select v-model="newCategory" class="select cat" aria-label="新标签的渲染类别">
                <option value="" disabled>类别</option>
                <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.label }}</option>
              </select>
              <button class="btn" type="button" :disabled="!newTagName || !newCategory || !!addProblem" @click="addTag"><Plus /> 添加</button>
            </div>
            <p v-if="addProblem" class="hint warn">{{ addProblem }}</p>
            <div class="card card-pad page-surface"><OutputView :text="sample" /></div>
          </section>

          <RouterLink to="/data" class="card link-row">
            <Database class="link-icon" />
            <div class="grow">
              <div class="name">聊天数据</div>
              <div class="faint small">直接查看和批量修改所有数据</div>
            </div>
            <ChevronRight class="chev" />
          </RouterLink>

          <div><button class="btn" type="button" @click="reset"><RotateCcw /> 恢复默认设置</button></div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings { display: flex; flex-direction: column; height: 100%; }
.settings .page { flex: 1; }
.inner { max-width: 760px; margin: 0 auto; padding: var(--space-8) var(--space-6) var(--space-12); gap: var(--space-4); }
.display { font-family: var(--font-reading); font-size: var(--text-display); font-weight: 600; letter-spacing: 0.06em; }
.narrow-only { display: none; }

.section-nav { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--border); margin-bottom: var(--space-2); overflow-x: auto; scrollbar-width: none; }
.section-nav a {
  padding: var(--space-2) var(--space-3); color: var(--text-muted); text-decoration: none; font-weight: 500; font-size: var(--text-lg);
  border-bottom: 2px solid transparent; margin-bottom: -1px; white-space: nowrap;
}
.section-nav a:hover { color: var(--text); }
.section-nav a.on { color: var(--text); border-bottom-color: var(--accent); }

.rows { display: flex; flex-direction: column; padding: var(--space-1) var(--space-4); }
.setting {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-2) var(--space-4);
  min-height: 56px; padding: var(--space-2) 0; border-bottom: 1px solid var(--border); cursor: default;
}
label.setting { cursor: pointer; }
.rows > .setting:last-child { border-bottom: 0; }
.setting.sub { min-height: 44px; padding-left: var(--space-4); }
.name { display: inline-flex; align-items: center; gap: var(--space-1); font-weight: 500; }
.select.narrow { width: 200px; }
.range-row { gap: var(--space-3); }
.range-row input { width: 200px; accent-color: var(--accent); }
.value { min-width: 48px; text-align: right; font-variant-numeric: tabular-nums; color: var(--text-muted); font-size: var(--text-sm); }
.font-preview { margin: var(--space-2) 0 var(--space-3); }
.font-preview .reading-prose { margin: 0; }
.summary-sample { margin: var(--space-3) 0 0; font-family: var(--font-reading); font-size: var(--text-sm); line-height: 1.65; color: var(--page-muted); }

.tag-table { display: flex; flex-direction: column; gap: var(--space-1-5); }
.tag-row { display: flex; align-items: center; gap: var(--space-2); }
.mode { width: 96px; flex-shrink: 0; }
.cat { width: 110px; flex-shrink: 0; }
.add-row .input { min-width: 160px; }
.add-row .cat { width: auto; }
.btn-spacer { width: 30px; flex-shrink: 0; }

.link-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); color: var(--text); text-decoration: none; }
.link-row:hover { background: var(--bg-hover); }
.link-icon { width: 20px; height: 20px; color: var(--text-muted); }
.chev { width: 18px; height: 18px; color: var(--text-faint); }
.small { font-size: var(--text-xs); }
@media (max-width: 899px) {
  .narrow-only { display: flex; }
  .inner { padding: var(--space-5) var(--space-4) var(--space-12); }
  .display { font-size: var(--text-3xl); }
  .range-row input { width: 150px; }
}
</style>
