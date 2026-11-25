<script setup lang="ts">
import { computed } from 'vue'
import { KeyRound, Plus } from 'lucide-vue-next'
import ProfileCover from '../ProfileCover.vue'
import { kindInfo, type LibraryKind } from './kinds'

export interface CardItem {
  id: string
  name: string
  sub?: string
  avatar?: string | null
  portrait?: string | null
  badge?: string
  hasKey?: boolean
}

/** One kind's records as cards: covers for people, compact cards for settings. */
const props = defineProps<{ kind: LibraryKind; items: CardItem[] }>()
const info = computed(() => kindInfo(props.kind))
const isProfile = computed(() => info.value.group === 'profiles')
const oneLine = (text?: string) => text?.replace(/\s+/g, ' ').trim() ?? ''
</script>

<template>
  <div v-if="isProfile" class="covers">
    <RouterLink v-for="it in items" :key="it.id" :to="`/library/${kind}/${it.id}`" class="cover-card">
      <ProfileCover :name="it.name" :portrait="it.portrait" :avatar="it.avatar">
        <span class="name ellipsis">{{ it.name }}</span>
        <span class="tagline">{{ oneLine(it.sub) }}</span>
      </ProfileCover>
    </RouterLink>
    <RouterLink :to="`/library/${kind}/new`" class="cover-card new"><Plus /><span>新建{{ info.noun }}</span></RouterLink>
  </div>
  <div v-else class="cards">
    <RouterLink v-for="it in items" :key="it.id" :to="`/library/${kind}/${it.id}`" class="card-item">
      <component :is="info.icon" class="icon" />
      <div class="grow">
        <div class="row tight"><span class="card-name ellipsis">{{ it.name }}</span><span v-if="it.badge" class="badge accent">{{ it.badge }}</span></div>
        <div v-if="it.sub" class="card-sub ellipsis">{{ it.sub }}</div>
      </div>
      <KeyRound v-if="it.hasKey" class="key" aria-label="已保存密钥" />
    </RouterLink>
    <RouterLink :to="`/library/${kind}/new`" class="card-item new"><Plus class="icon" /><span>新建{{ info.noun }}</span></RouterLink>
  </div>
</template>

<style scoped>
.covers { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-4); }
.cover-card {
  display: block; border-radius: var(--radius-l); overflow: hidden; color: inherit; text-decoration: none;
  box-shadow: var(--shadow); transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.cover-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-pop); }
.name { display: block; font-family: var(--font-reading); font-size: var(--text-2xl); font-weight: 600; line-height: 1.25; }
/* Fixed two-line height, so names line up across cards. */
.tagline { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: calc(2 * 1.5em); margin-top: var(--space-1); font-size: var(--text-xs); line-height: 1.5; opacity: 0.85; }
.cover-card.new {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2);
  aspect-ratio: 3 / 4; border: 1.5px dashed var(--border-strong); box-shadow: none; color: var(--text-muted);
}
.cover-card.new:hover, .card-item.new:hover { border-color: var(--accent); color: var(--accent); box-shadow: none; transform: none; }
.cover-card.new svg { width: 28px; height: 28px; }

.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--space-3); }
.card-item {
  display: flex; align-items: center; gap: var(--space-3); min-height: 76px; padding: var(--space-4);
  border: 1px solid var(--border); border-radius: var(--radius-l); background: var(--bg-elev); color: var(--text); text-decoration: none;
}
.card-item:hover { border-color: var(--border-strong); background: var(--bg-hover); }
.card-item.new { border-style: dashed; color: var(--text-muted); background: none; justify-content: center; }
.icon { width: 22px; height: 22px; flex-shrink: 0; color: var(--accent); stroke-width: 1.6; }
.card-item.new .icon { color: inherit; }
.tight { gap: var(--space-1-5); }
.card-name { font-weight: 600; font-size: var(--text-lg); }
.card-sub { font-size: var(--text-xs); color: var(--text-faint); margin-top: 2px; }
.key { width: 15px; height: 15px; color: var(--ok); flex-shrink: 0; }
@media (max-width: 899px) {
  .covers { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
  .name { font-size: var(--text-xl); }
}
</style>
