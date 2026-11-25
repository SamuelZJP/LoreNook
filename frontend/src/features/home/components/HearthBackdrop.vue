<script setup lang="ts">
/** The room behind the public pages: firelight and embers at night, window light by day. Decoration only. */
defineProps<{ night: boolean }>()

/** Fixed pseudo-random embers, so the scene is the same on every visit. */
const embers = Array.from({ length: 34 }, (_, k) => {
  const r = (n: number) => {
    const x = Math.sin((k + 1) * n * 78.233) * 12345.678
    return x - Math.floor(x)
  }
  const size = 1.5 + r(2.3) * 2.6
  return {
    left: `${(32 + r(1.1) * 36).toFixed(1)}%`,
    width: `${size.toFixed(1)}px`,
    height: `${size.toFixed(1)}px`,
    animationDuration: `${(6 + r(3.7) * 7).toFixed(1)}s`,
    animationDelay: `-${(r(4.9) * 12).toFixed(1)}s`,
    '--drift': `${((r(5.3) - 0.5) * 220).toFixed(0)}px`,
  }
})
</script>

<template>
  <div class="backdrop" aria-hidden="true">
    <template v-if="night">
      <div class="layer planks" />
      <div class="glow far" />
      <div class="glow near" />
      <div class="glow core" />
      <span v-for="(style, i) in embers" :key="i" class="ember" :style="style" />
      <div class="layer vignette" />
    </template>
    <template v-else>
      <div class="layer sun" />
      <div class="window" />
      <div class="layer planks" />
    </template>
  </div>
</template>

<style scoped>
.backdrop, .layer { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.planks {
  background: repeating-linear-gradient(90deg, transparent 0 159px, var(--h-faint) 159px 160px);
  mask-image: radial-gradient(ellipse 70% 80% at 50% 100%, #000 0%, transparent 75%); opacity: 0.6;
}
.glow { position: absolute; left: 50%; transform: translateX(-50%); }
.far {
  bottom: -46vh; width: 150vw; height: 110vh;
  background: radial-gradient(closest-side, rgb(255 128 44 / 34%), rgb(190 72 22 / 14%) 48%, transparent 78%);
  animation: breathe 7s ease-in-out infinite;
}
.near {
  bottom: -20vh; width: 62vw; height: 48vh; mix-blend-mode: screen;
  background: radial-gradient(closest-side, rgb(255 196 120 / 42%), rgb(255 130 50 / 16%) 55%, transparent 80%);
  animation: flicker 3.1s steps(1, end) infinite, breathe 4.3s ease-in-out infinite;
}
.core {
  bottom: -9vh; width: 22vw; height: 20vh; mix-blend-mode: screen; filter: blur(6px);
  background: radial-gradient(closest-side, rgb(255 226 170 / 55%), rgb(255 160 80 / 20%) 60%, transparent 85%);
  animation: flicker2 2.3s ease-in-out infinite;
}
.vignette { background: radial-gradient(ellipse 85% 75% at 50% 45%, transparent 45%, rgb(0 0 0 / 60%) 100%); }
.ember {
  position: absolute; bottom: -12px; border-radius: 50%; background: #ffc27a; opacity: 0;
  box-shadow: 0 0 6px 2px rgb(255 140 60 / 55%);
  animation-name: rise; animation-timing-function: linear; animation-iteration-count: infinite;
}
.sun {
  background:
    radial-gradient(ellipse 60% 55% at 12% -5%, rgb(255 240 212 / 95%), transparent 70%),
    radial-gradient(ellipse 50% 40% at 100% 110%, rgb(176 128 84 / 10%), transparent 70%);
}
.window {
  position: absolute; top: -10%; left: 6%; width: 38vw; height: 120%; opacity: 0.55; transform: skewX(-14deg);
  background: linear-gradient(100deg, rgb(255 248 232 / 0%) 0%, rgb(255 248 232 / 55%) 30%, rgb(255 248 232 / 0%) 60%);
}
@keyframes rise {
  0% { transform: translate(0, 0) scale(1); opacity: 0; }
  8% { opacity: 0.95; }
  60% { opacity: 0.55; }
  100% { transform: translate(var(--drift), -78vh) scale(0.3); opacity: 0; }
}
@keyframes breathe {
  0%, 100% { opacity: 0.85; transform: translateX(-50%) scale(1); }
  50% { opacity: 1; transform: translateX(-50%) scale(1.04); }
}
@keyframes flicker {
  0% { opacity: 0.9; } 13% { opacity: 0.75; } 21% { opacity: 1; } 34% { opacity: 0.82; }
  47% { opacity: 0.95; } 58% { opacity: 0.7; } 71% { opacity: 1; } 86% { opacity: 0.86; }
}
@keyframes flicker2 {
  0%, 100% { opacity: 0.8; transform: translateX(-50%) scale(1, 1); }
  30% { opacity: 1; transform: translateX(-51%) scale(1.06, 1.12); }
  55% { opacity: 0.7; transform: translateX(-49%) scale(0.96, 0.94); }
  80% { opacity: 0.95; transform: translateX(-50%) scale(1.03, 1.08); }
}
@media (prefers-reduced-motion: reduce) {
  .ember { display: none; }
  .far, .near, .core { animation: none; }
}
</style>
