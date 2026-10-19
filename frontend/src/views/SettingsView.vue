<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Trash2, RotateCcw } from 'lucide-vue-next'
import TopBar from '@/components/TopBar.vue'
import OutputView from '@/components/chat/OutputView.vue'
import { prefs, resetPrefs, type SectionMode } from '@/lib/prefs'

const modes: { id: SectionMode; label: string }[] = [
  { id: 'show', label: '显示' },
  { id: 'collapse', label: '折叠' },
  { id: 'hide', label: '隐藏' },
]
const newTag = ref('')
function addTag() {
  const name = newTag.value.trim().replace(/^<|>$/g, '')
  if (name && !(name in prefs.sections)) prefs.sections[name] = 'collapse'
  newTag.value = ''
}
function removeTag(name: string) {
  delete prefs.sections[name]
}
function reset() {
  if (confirm('恢复所有界面偏好为默认值？')) resetPrefs()
}

const sample = `<think>这是预设自定义的思考区段，不是模型原生推理。</think>
<content>“早上好。”她把书合上，**抬起头**看向你。

窗外的雨还没有停。</content>
<status>好感度 +1</status>`
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
        </section>

        <section class="card card-pad stack">
          <h2>输出解析与显示</h2>
          <p class="hint">AI 输出按顶层标签拆分为区段。这些设置只影响显示，确认与存储的始终是完整原文。</p>
          <label class="check"><input v-model="prefs.markdown" type="checkbox" /> 用 Markdown 渲染（HTML 标签会被转义，不会执行）</label>
          <div class="tag-table">
            <div v-for="(_mode, name) in prefs.sections" :key="name" class="tag-row">
              <code class="grow">&lt;{{ name }}&gt;</code>
              <select v-model="prefs.sections[name]" class="select mode">
                <option v-for="m in modes" :key="m.id" :value="m.id">{{ m.label }}</option>
              </select>
              <button class="btn ghost icon small" type="button" :title="`移除 ${name}`" @click="removeTag(String(name))"><Trash2 /></button>
            </div>
            <div class="tag-row">
              <span class="grow">其他未列出的标签</span>
              <select v-model="prefs.unknownSection" class="select mode">
                <option v-for="m in modes" :key="m.id" :value="m.id">{{ m.label }}</option>
              </select>
              <span class="btn-spacer" />
            </div>
            <div class="tag-row">
              <span class="grow">标签外的文本</span>
              <select v-model="prefs.looseText" class="select mode">
                <option v-for="m in modes" :key="m.id" :value="m.id">{{ m.label }}</option>
              </select>
              <span class="btn-spacer" />
            </div>
          </div>
          <div class="row">
            <input v-model="newTag" class="input" placeholder="添加标签名，例如 report_nya~" @keydown.enter="addTag" />
            <button class="btn" type="button" @click="addTag"><Plus /> 添加</button>
          </div>
          <div class="label">预览</div>
          <div class="card card-pad preview"><OutputView :text="sample" /></div>
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
        </section>

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
.mode { width: 110px; }
.btn-spacer { width: 28px; flex-shrink: 0; }
.preview { background: var(--bubble-ai); }
input[type='range'] { accent-color: var(--accent); }
</style>
