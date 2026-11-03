<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Plus, Trash2, RotateCcw } from 'lucide-vue-next'
import TopBar from '@/components/TopBar.vue'
import OutputView from '@/components/chat/OutputView.vue'
import { categoryDefaultMode, prefs, resetPrefs, REPLY_CAP_RANGE, type RenderCategory, type SectionMode } from '@/lib/prefs'
import { EN_FONTS, ZH_FONTS } from '@/lib/fonts'
import BackdropPreference from '@/features/illustrations/components/BackdropPreference.vue'

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
// Floor limit: the field keeps the last valid number while "unlimited" is on.
const limitDraft = ref(String(prefs.floorLimit ?? 100))
const limitProblem = computed(() => (/^[1-9]\d*$/.test(limitDraft.value.trim()) ? null : '请输入正整数'))
watch(() => prefs.floorLimit, (v) => { if (v !== null) limitDraft.value = String(v) })
function commitLimit() {
  if (!limitProblem.value) prefs.floorLimit = Number(limitDraft.value.trim())
}
function setUnlimited(on: boolean) {
  prefs.floorLimit = on ? null : limitProblem.value ? 100 : Number(limitDraft.value.trim())
}

// Reply height limit: same draft pattern as the floor limit.
const capDraft = ref(String(prefs.replyCap ?? 100))
const capProblem = computed(() => {
  const text = capDraft.value.trim()
  const n = Number(text)
  return /^\d+$/.test(text) && n >= REPLY_CAP_RANGE.min && n <= REPLY_CAP_RANGE.max ? null : `请输入 ${REPLY_CAP_RANGE.min}–${REPLY_CAP_RANGE.max} 的整数`
})
watch(() => prefs.replyCap, (v) => { if (v !== null) capDraft.value = String(v) })
function commitCap() {
  if (!capProblem.value) prefs.replyCap = Number(capDraft.value.trim())
}
function setCapOff(off: boolean) {
  prefs.replyCap = off ? null : capProblem.value ? 100 : Number(capDraft.value.trim())
}

const fontSample = `窗外的雨停了。她翻开那本 The Little Prince（1943 年初版），轻声念道："All grown-ups were once children." 然后合上书，说："我们走吧。"`

function reset() {
  if (confirm('恢复所有界面偏好为默认值？')) resetPrefs()
}

const sample = `<think>她还不确定该不该提起那封信，也许先试探一下。这是预设自定义的思考区段，不是模型原生推理。</think>
<content>凌晨 3:40，雨势小了些。她把那本 1998 年版的《Le Petit Prince》合上，指尖在封面上停了很久，才轻声说了句“随便你吧”，像是在对自己说。
“你来得太晚了。”
“走吧。”她站起身，把伞递给你。

所谓“规矩”，在这间旧书店里从来只有一条——不许在第 7 排书架前说谎。
「那封信……『你』真的读过吗？」
【喂？听得到吗？这里信号不太好。】</content>
<status>好感度 62 → 63 · 第 3 天 21:40</status>`
</script>

<template>
  <div class="settings">
    <TopBar><h1 class="grow">设置</h1></TopBar>
    <div class="page">
      <div class="page-inner narrow stack">
        <p class="hint">以下偏好只保存在当前浏览器（localStorage）中，不会同步到其他设备或浏览器，也不属于后端数据。聊天记忆（X / Y）、预设和模型绑定在各聊天的设置面板中修改；模型配置在资源库中管理。部分摘要上下文窗口（状态更新与回合摘要读取的近期摘要数）是后端服务器配置，不能在网页中修改。</p>

        <section class="card card-pad stack">
          <h2>外观</h2>
          <div class="field">
            <label>主题</label>
            <div class="row wrap seg">
              <label v-for="t in [['system', '跟随系统'], ['light', '浅色'], ['dark', '深色']]" :key="t[0]" class="check">
                <input v-model="prefs.theme" type="radio" :value="t[0]" /> {{ t[1] }}
              </label>
            </div>
          </div>
          <div class="field">
            <label>正文字号：{{ prefs.fontSize }}px</label>
            <input v-model.number="prefs.fontSize" type="range" min="13" max="22" step="1" />
          </div>
          <div class="row wrap font-row">
            <div class="field grow">
              <label for="zh-font">中文字体</label>
              <select id="zh-font" v-model="prefs.zhFont" class="select">
                <option v-for="f in ZH_FONTS" :key="f.id" :value="f.id">{{ f.label }}</option>
              </select>
            </div>
            <div class="field grow">
              <label for="en-font">英文字体</label>
              <select id="en-font" v-model="prefs.enFont" class="select">
                <option v-for="f in EN_FONTS" :key="f.id" :value="f.id">{{ f.label }}</option>
              </select>
            </div>
          </div>
          <div class="card card-pad page-surface font-preview">
            <p class="reading-prose">{{ fontSample }}</p>
            <p class="summary-sample">回合摘要：她在雨夜读完 The Little Prince，决定和你一起离开书店。</p>
          </div>
          <p class="hint">用于聊天正文和回合摘要。除思源宋体随应用加载外，其他字体取决于设备是否安装，缺少时会自动改用相近字体。代码与界面文字不受影响。</p>
        </section>

        <section class="card card-pad stack">
          <h2>输出解析与显示</h2>
          <p class="hint">AI 输出按顶层标签拆分为区段。这些设置只影响显示，确认与存储的始终是完整原文。</p>
          <label class="check"><input v-model="prefs.markdown" type="checkbox" /> 用 Markdown 渲染（HTML 标签会被转义，不会执行）</label>
          <div class="tag-table">
            <div class="tag-row head faint">
              <span class="grow">标签</span><span class="cat">渲染类别</span><span class="mode">显示方式</span><span class="btn-spacer" />
            </div>
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
            <div v-for="row in [{ rule: prefs.unknownSection, label: '其他未列出的标签' }, { rule: prefs.looseText, label: '标签外的文本' }]" :key="row.label" class="tag-row">
              <span class="grow">{{ row.label }}</span>
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
            <input v-model="newTag" class="input grow" placeholder="添加标签名，例如 report_nya~" @keydown.enter="addTag" />
            <select v-model="newCategory" class="select cat" aria-label="新标签的渲染类别">
              <option value="" disabled>选择渲染类别</option>
              <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.label }}</option>
            </select>
            <button class="btn" type="button" :disabled="!newTagName || !newCategory || !!addProblem" @click="addTag"><Plus /> 添加</button>
          </div>
          <p v-if="addProblem" class="hint warn-text">{{ addProblem }}</p>
          <p class="hint">渲染类别决定区段的样式：正文使用书页排版并标出对白引号；思维链显示为可展开的批注；其他内容显示为紧凑的附注。显示方式决定是否展开或隐藏。</p>
          <div class="label">预览</div>
          <div class="card card-pad page-surface"><OutputView :text="sample" /></div>
        </section>

        <section class="card card-pad stack">
          <h2>对话</h2>
          <div class="field">
            <label>发送快捷键</label>
            <div class="row wrap seg">
              <label class="check"><input v-model="prefs.sendKey" type="radio" value="ctrl-enter" /> Ctrl/⌘ + Enter 发送</label>
              <label class="check"><input v-model="prefs.sendKey" type="radio" value="enter" /> Enter 发送，Shift + Enter 换行</label>
            </div>
          </div>
          <label class="check"><input v-model="prefs.showFloorNumbers" type="checkbox" /> 显示楼层编号</label>
          <label class="check"><input v-model="prefs.showSummaries" type="checkbox" /> 默认展开回合摘要</label>
          <div class="field">
            <label for="floor-limit">楼层显示上限</label>
            <div class="row wrap limit-row">
              <input
                id="floor-limit" v-model="limitDraft" class="input limit" inputmode="numeric"
                :disabled="prefs.floorLimit === null" :aria-invalid="!!limitProblem" @input="commitLimit"
              />
              <span class="faint">层</span>
              <label class="check"><input type="checkbox" :checked="prefs.floorLimit === null" @change="setUnlimited(($event.target as HTMLInputElement).checked)" /> 不限制</label>
            </div>
            <p v-if="limitProblem && prefs.floorLimit !== null" class="hint warn-text">{{ limitProblem }}</p>
            <p class="hint">只显示最近的楼层，可在聊天顶部加载更早的楼层。不影响聊天记录和发送给模型的上下文。</p>
          </div>
          <div class="field">
            <label for="reply-cap">回复框高度上限</label>
            <div class="row wrap limit-row">
              <input
                id="reply-cap" v-model="capDraft" class="input limit" inputmode="numeric"
                :disabled="prefs.replyCap === null" :aria-invalid="!!capProblem" @input="commitCap"
              />
              <span class="faint">% 聊天区高度</span>
              <label class="check"><input type="checkbox" :checked="prefs.replyCap === null" @change="setCapOff(($event.target as HTMLInputElement).checked)" /> 不限制</label>
            </div>
            <p v-if="capProblem && prefs.replyCap !== null" class="hint warn-text">{{ capProblem }}</p>
            <p class="hint">超出上限时正文在回复框内滚动，插图和状态栏保持可见。正文至少保留几行高度。</p>
          </div>
        </section>

        <BackdropPreference />

        <div><button class="btn" type="button" @click="reset"><RotateCcw /> 恢复默认</button></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings { display: flex; flex-direction: column; height: 100%; }
.settings .page { flex: 1; }
.narrow { max-width: 720px; }
.seg { gap: 16px; }
.tag-table { display: flex; flex-direction: column; gap: 6px; }
.tag-row { display: flex; align-items: center; gap: 8px; }
.mode { width: 96px; flex-shrink: 0; }
.cat { width: 110px; flex-shrink: 0; }
.head { font-size: 12px; }
.add-row .input { min-width: 180px; }
.add-row .cat { width: auto; }
.warn-text { color: var(--warn); }
.btn-spacer { width: 28px; flex-shrink: 0; }
input[type='range'] { accent-color: var(--accent); }
.font-row { gap: 12px; align-items: flex-start; }
.font-row .field { min-width: 160px; }
.font-preview .reading-prose { margin: 0; }
.summary-sample { margin: 10px 0 0; font-family: var(--font-reading); font-size: 13px; line-height: 1.65; color: var(--page-muted); }
.limit-row { gap: 8px; }
.limit { width: 96px; }
</style>
