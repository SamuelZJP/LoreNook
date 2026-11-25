<script setup lang="ts">
/** "Lore Nook" large and see-through, with 炉隅 solid in front of it. */
withDefaults(defineProps<{ size?: 'hero' | 'compact'; tag?: 'h1' | 'div' }>(), { size: 'hero', tag: 'h1' })
</script>

<template>
  <div class="wordmark" :class="`is-${size}`">
    <div class="latin" aria-hidden="true">Lore Nook</div>
    <component :is="tag" class="cn">炉隅<span class="visually-hidden"> Lore Nook</span></component>
  </div>
</template>

<style scoped>
.wordmark { position: relative; display: grid; place-items: center; }
.latin {
  font-family: var(--h-latin); font-weight: 300; line-height: 0.86; letter-spacing: -0.01em; white-space: nowrap;
  font-size: clamp(88px, 19vw, 300px); color: transparent; background-clip: text; -webkit-background-clip: text; user-select: none;
}
.is-compact .latin { font-size: clamp(72px, 14vw, 180px); }
.night .latin {
  background-image: linear-gradient(to top, rgb(255 176 98 / 62%) 0%, rgb(255 206 150 / 26%) 42%, rgb(239 227 211 / 7%) 100%);
}
.day .latin {
  opacity: 0.42;
  background-image:
    repeating-linear-gradient(91deg, rgb(90 52 24 / 0%) 0 3px, rgb(90 52 24 / 22%) 3px 4px, rgb(90 52 24 / 0%) 4px 9px),
    repeating-linear-gradient(87deg, rgb(255 230 200 / 18%) 0 13px, rgb(100 60 30 / 14%) 13px 23px),
    linear-gradient(180deg, #b07a4c, #8a5a34 60%, #6e4426);
}
.cn {
  position: absolute; margin: 0; font-family: var(--h-serif); font-weight: 600; line-height: 1; color: var(--h-ink);
  font-size: clamp(40px, 5.4vw, 80px); letter-spacing: 0.42em; padding-left: 0.42em;
}
.is-compact .cn { font-size: clamp(32px, 4vw, 52px); }
.night .cn { text-shadow: 0 0 40px rgb(255 150 70 / 25%); }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
</style>
