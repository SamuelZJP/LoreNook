<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft, Pencil, Play } from 'lucide-vue-next'
import TopBar from '@/components/TopBar.vue'
import ProfileCover from '@/components/ProfileCover.vue'
import ProfilePicker from '@/components/ProfilePicker.vue'
import Disclosure from '@/components/Disclosure.vue'
import ChatParamsFields from '@/components/ChatParamsFields.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ScrollRow from '@/components/ScrollRow.vue'
import { useChatStart } from '@/composables/chatStart'
import { isDemo } from '@/features/account/session'
import { contentBody } from '@/lib/sections'

/** A character's page: who they are, their openings, and starting a chat. */
const props = defineProps<{ id: string }>()
const {
  characters, character, scenes, form, identities, presets, models, templates, template, templateId, titleTouched,
  params, paramsReady, create, canStart, saveAs, saveTemplate,
} = useChatStart(computed(() => props.id))

// The parameters component is reached through the composable's ref.
function setParams(el: unknown) { params.value = (el ?? undefined) as typeof params.value }
const openingOf = (text: string) => contentBody(text).replace(/\s+/g, ' ').trim()
</script>

<template>
  <div class="character-view">
    <TopBar>
      <RouterLink to="/hall" class="btn ghost small"><ArrowLeft /> 角色</RouterLink>
      <span class="grow" />
      <RouterLink v-if="character && !isDemo" :to="`/library/characters/${id}`" class="btn ghost small"><Pencil /> 编辑</RouterLink>
    </TopBar>
    <div class="page">
      <ErrorBox v-if="characters.error.value" :error="characters.error.value" />
      <div v-else-if="characters.isPending.value" class="empty">加载中…</div>
      <div v-else-if="!character" class="empty">找不到这个角色</div>
      <div v-else class="hero">
        <ProfileCover class="hero-cover" :name="character.name" :portrait="character.portrait" :avatar="character.avatar" />
        <div class="info stack">
          <h1 class="display">{{ character.name }}</h1>
          <p v-if="character.description" class="desc">{{ character.description }}</p>

          <h2 class="section">{{ scenes.length > 1 ? '选择开场' : '开场' }}</h2>
          <ScrollRow class="scenes">
            <button
              v-for="sc in scenes" :key="sc.id" type="button" class="scene" :class="{ active: form.scene_id === sc.id }"
              :aria-pressed="form.scene_id === sc.id" @click="form.scene_id = sc.id"
            >
              <span class="scene-name">{{ sc.name }}</span>
              <span v-if="sc.description" class="scene-desc">{{ sc.description }}</span>
              <span v-if="openingOf(sc.first_message)" class="scene-text">{{ openingOf(sc.first_message) }}</span>
            </button>
          </ScrollRow>

          <div class="start">
            <template v-if="identities.data.value?.length">
              <span class="muted as">你的身份</span>
              <ProfilePicker v-model="form.user_identity_id" :items="identities.data.value" label="你的身份" class="who" />
            </template>
            <RouterLink v-else-if="!identities.isPending.value" to="/library/identities/new" class="btn">先创建你的身份</RouterLink>
            <button class="btn accent big" type="button" :disabled="!canStart" @click="create.mutate()">
              <Play /> {{ create.isPending.value ? '准备中…' : '开始聊天' }}
            </button>
          </div>
          <ErrorBox v-if="create.error.value" :error="create.error.value" title="没能开始聊天" />

          <Disclosure>
            <template #summary><span class="faint"> · {{ template?.name ?? '默认设置' }}</span></template>
            <div class="grid-2">
              <div class="field">
                <label>聊天标题</label>
                <input v-model="form.title" class="input" @input="titleTouched = true" />
              </div>
              <div v-if="templates.data.value?.length" class="field">
                <label>开局模板</label>
                <select v-model="templateId" class="select">
                  <option value="">（默认设置）</option>
                  <option v-for="t in templates.data.value" :key="t.id" :value="t.id">{{ t.name }}{{ t.is_default ? '（默认）' : '' }}</option>
                </select>
              </div>
            </div>
            <ChatParamsFields
              v-if="paramsReady" :ref="setParams" :key="templateId"
              :presets="presets.data.value ?? []" :models="models.data.value ?? []" :initial="template?.settings ?? null"
            />
            <div class="save-as">
              <h3>另存为模板</h3>
              <div class="row wrap">
                <input v-model="saveAs.name" class="input grow" placeholder="模板名称" />
                <label class="check"><input v-model="saveAs.is_default" type="checkbox" /> 设为默认</label>
                <button class="btn small" type="button" :disabled="!saveAs.name.trim() || saveTemplate.isPending.value" @click="saveTemplate.mutate()">保存</button>
              </div>
              <ErrorBox v-if="saveTemplate.error.value" :error="saveTemplate.error.value" title="模板保存失败" />
            </div>
          </Disclosure>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.character-view { display: flex; flex-direction: column; height: 100%; }
.character-view .page { flex: 1; }
.hero {
  display: flex; gap: var(--space-8); align-items: flex-start; flex-wrap: wrap;
  max-width: 1080px; margin: 0 auto; padding: var(--space-8) var(--space-6) var(--space-12);
}
.hero-cover { width: 320px; flex-shrink: 0; border-radius: var(--radius-xl); box-shadow: var(--shadow); position: sticky; top: var(--space-6); }
.info { flex: 1; min-width: 300px; gap: var(--space-4); }
.display { font-family: var(--font-reading); font-size: var(--text-display); font-weight: 600; letter-spacing: 0.02em; line-height: 1.15; }
.desc { font-family: var(--font-reading); font-size: var(--text-lg); line-height: 1.8; color: var(--text-muted); white-space: pre-wrap; }
.section { margin-top: var(--space-3); font-size: var(--text-sm); font-weight: 600; color: var(--text-muted); letter-spacing: 0.08em; }
/* One row of equal cards; more openings scroll sideways. */
.scene {
  flex: 0 0 260px; min-height: 120px;
  display: flex; flex-direction: column; gap: var(--space-1-5); padding: var(--space-4); text-align: left;
  border: 1px solid var(--border); border-radius: var(--radius-l); background: var(--bg-elev);
  font: inherit; color: inherit; cursor: pointer; transition: border-color 0.12s, background 0.12s;
}
.scene:hover { border-color: var(--border-strong); }
.scene.active { border-color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 1px var(--accent); }
.scene-name { font-family: var(--font-reading); font-size: var(--text-xl); font-weight: 600; }
.scene-desc { font-size: var(--text-sm); color: var(--text-muted); }
.scene-text {
  font-family: var(--font-reading); font-size: var(--text-sm); line-height: 1.7; color: var(--text-muted);
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.start { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-2); }
.as { font-size: var(--text-sm); }
.who { width: 240px; }
.big { min-height: 44px; padding: 0 var(--space-6); font-size: var(--text-lg); margin-left: auto; }
.big svg { width: 18px; height: 18px; }
.save-as { border-top: 1px solid var(--border); padding-top: var(--space-3); display: flex; flex-direction: column; gap: var(--space-2); }
@media (max-width: 899px) {
  .hero { flex-direction: column; align-items: stretch; padding: var(--space-4) var(--space-4) var(--space-12); gap: var(--space-5); }
  .hero-cover { position: relative; top: 0; width: min(260px, 70vw); margin: 0 auto; }
  .info { min-width: 0; }
  .display { font-size: var(--text-3xl); text-align: center; }
  .big { width: 100%; margin-left: 0; }
  .who { flex: 1; }
}
</style>
