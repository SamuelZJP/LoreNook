<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { ArrowRight, Cpu, Feather, Plus, UserRound } from 'lucide-vue-next'
import { api } from '@/api/endpoints'
import TopBar from '@/components/TopBar.vue'
import ProfileCover from '@/components/ProfileCover.vue'
import ErrorBox from '@/components/ErrorBox.vue'
import ScrollRow from '@/components/ScrollRow.vue'
import { formatTime } from '@/lib/format'

const characters = useQuery({ queryKey: ['characters'], queryFn: api.characters })
const identities = useQuery({ queryKey: ['identities'], queryFn: api.identities })
const presets = useQuery({ queryKey: ['presets', null], queryFn: () => api.presets({ chatId: null }) })
const models = useQuery({ queryKey: ['models', null], queryFn: () => api.models({ chatId: null }) })
const chats = useQuery({ queryKey: ['chats'], queryFn: api.chats })
const health = useQuery({ queryKey: ['health'], queryFn: () => fetch('/health').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))), retry: 0 })

const recent = computed(() => (chats.data.value ?? []).slice(0, 8))

// What is still missing before a chat can run; shown only until it's done.
const setup = computed(() => [
  { show: models.data.value && !models.data.value.length, icon: Cpu, label: '连接 AI 模型', to: '/library/models/new' },
  { show: presets.data.value && !presets.data.value.length, icon: Feather, label: '添加写作风格', to: '/library/presets/new' },
  { show: identities.data.value && !identities.data.value.length, icon: UserRound, label: '创建你的身份', to: '/library/identities/new' },
].filter((s) => s.show))

const tagline = (text?: string | null) => text?.replace(/\s+/g, ' ').trim() ?? ''
</script>

<template>
  <div class="home">
    <TopBar class="home-bar"><strong class="grow brand">LoreNook</strong></TopBar>
    <div class="page">
      <div class="inner">
        <div v-if="health.error.value" class="card card-pad offline">
          <strong>连接不上服务。</strong>请确认 LoreNook 后端正在运行。
        </div>

        <section v-if="setup.length" class="setup">
          <h2 class="title">开始之前</h2>
          <div class="setup-row">
            <RouterLink v-for="s in setup" :key="s.label" :to="s.to" class="setup-item">
              <component :is="s.icon" class="setup-icon" />
              <span class="grow">{{ s.label }}</span>
              <ArrowRight class="arrow" />
            </RouterLink>
          </div>
        </section>

        <section v-if="recent.length" class="block">
          <h2 class="title">继续</h2>
          <ScrollRow>
            <RouterLink v-for="c in recent" :key="c.id" :to="`/chats/${c.id}`" class="recent-card">
              <ProfileCover :name="c.title" :portrait="c.portrait" :avatar="c.avatar">
                <span class="caption-title ellipsis">{{ c.title }}</span>
                <span class="caption-line">{{ c.last_line || formatTime(c.created_at) }}</span>
              </ProfileCover>
            </RouterLink>
          </ScrollRow>
        </section>

        <section class="block">
          <h2 class="title">角色</h2>
          <ErrorBox v-if="characters.error.value" :error="characters.error.value" />
          <div class="gallery">
            <RouterLink v-for="c in characters.data.value" :key="c.id" :to="`/characters/${c.id}`" class="card-link">
              <ProfileCover :name="c.name" :portrait="c.portrait" :avatar="c.avatar" class="gallery-cover">
                <span class="name ellipsis">{{ c.name }}</span>
                <span class="tagline">{{ tagline(c.description) }}</span>
              </ProfileCover>
            </RouterLink>
            <RouterLink to="/library/characters/new" class="card-link new-card">
              <Plus /><span>新角色</span>
            </RouterLink>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home { display: flex; flex-direction: column; height: 100%; }
.home .page { flex: 1; }
/* The bar only carries the menu button on narrow screens. */
.home-bar { display: none; }
@media (max-width: 899px) { .home-bar { display: flex; } }
.brand { font-family: var(--font-reading); font-size: var(--text-xl); }
.inner { max-width: 1200px; margin: 0 auto; padding: var(--space-8) var(--space-6) var(--space-12); display: flex; flex-direction: column; gap: var(--space-8); }
.title { font-family: var(--font-reading); font-size: var(--text-3xl); font-weight: 600; letter-spacing: 0.04em; margin-bottom: var(--space-4); }
.offline { background: var(--danger-soft); }

.setup-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); }
.setup-item {
  display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-radius: var(--radius-l);
  background: var(--accent-soft); color: var(--text); text-decoration: none; font-weight: 500;
}
.setup-item:hover { box-shadow: 0 0 0 1px var(--accent); }
.setup-icon { width: 22px; height: 22px; color: var(--accent); }
.arrow { width: 16px; height: 16px; color: var(--text-muted); }

.recent-card { flex: 0 0 160px; border-radius: var(--radius-l); overflow: hidden; color: inherit; text-decoration: none; }
/* Captions keep a fixed shape, so titles line up whatever the text below them. */
.caption-title { display: block; font-weight: 600; font-size: var(--text-sm); line-height: 1.4; }
.caption-line {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  height: calc(2 * 1.55em); margin-top: 2px; font-family: var(--font-reading); font-size: var(--text-xs); line-height: 1.55; opacity: 0.9;
}

.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-4); }
.card-link {
  display: block; border-radius: var(--radius-l); overflow: hidden; color: inherit; text-decoration: none;
  box-shadow: var(--shadow); transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.card-link:hover { transform: translateY(-3px); box-shadow: var(--shadow-pop); }
.name { display: block; font-family: var(--font-reading); font-size: var(--text-2xl); font-weight: 600; line-height: 1.25; }
.tagline {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  height: calc(2 * 1.5em); margin-top: var(--space-1); font-size: var(--text-xs); line-height: 1.5; opacity: 0.85;
}
.new-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2);
  aspect-ratio: 3 / 4; border: 1.5px dashed var(--border-strong); box-shadow: none; color: var(--text-muted);
}
.new-card:hover { border-color: var(--accent); color: var(--accent); box-shadow: none; }
.new-card svg { width: 28px; height: 28px; }
@media (max-width: 899px) {
  .inner { padding: var(--space-5) var(--space-4) var(--space-12); gap: var(--space-6); }
  .title { font-size: var(--text-2xl); }
  .gallery { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
  .name { font-size: var(--text-xl); }
}
</style>
