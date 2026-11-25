<script setup lang="ts">
import { computed } from 'vue'
import { resolvedTheme } from '@/lib/prefs'
import { account } from '@/features/account/session'
import HearthBackdrop from '@/features/home/components/HearthBackdrop.vue'
import HearthTopBar from '@/features/home/components/HearthTopBar.vue'
import WordMark from '@/features/home/components/WordMark.vue'
import { useHomeInfo } from '@/features/home/usePresence'
import '@/features/home/hearth.css'

const night = computed(() => resolvedTheme.value === 'dark')
const { online, icp } = useHomeInfo()
const enter = computed(() => (account.value ? { to: '/hall', label: '回到炉边' } : { to: '/login', label: '进入炉边' }))

const features = [
  { num: '壹', title: '有记性的故事', en: 'Memory that lingers', body: '近的事记得清，远的事记得要紧处。每一回落笔之前，它会先翻一翻旧账，把该想起的往事拾回来。' },
  { num: '贰', title: '会生长的世界', en: 'A world that keeps time', body: '日期、地点、人物与彼此的关系，随剧情一回一回地推移。世界自己记账，你只管往下写。' },
  { num: '叁', title: '一回一回地写', en: 'Told round by round', body: '每一回都能重写、斟酌、确认；写满一章便归档成卷，留下提要，回头翻阅也不费力。' },
  { num: '肆', title: '由你定的笔法', en: 'Your pen, your rules', body: '写作预设是一段可编程的脚本。语气、视角、篇幅与规矩，都由你说了算。' },
  { num: '伍', title: '带得走的角色', en: 'Characters to carry', body: '角色卡可导入导出，人设随身携带。换一处炉火，故事照旧续下去。' },
]
</script>

<template>
  <div class="hearth landing" :class="night ? 'night' : 'day'">
    <section class="hero">
      <HearthBackdrop :night="night" />
      <HearthTopBar />
      <div class="hero-body">
        <WordMark class="mark" />
        <p class="tagline">一篝炉火，半屋故事</p>
        <p class="sub">在木屋的一角，与你笔下的人物促膝长谈，直到柴尽灯残</p>
        <div class="actions">
          <RouterLink class="hearth-btn primary" :to="enter.to">{{ enter.label }}</RouterLink>
          <RouterLink v-if="!account" class="hearth-btn ghost" to="/register">注册</RouterLink>
        </div>
      </div>
      <div class="bottom">
        <p v-if="online !== null" class="presence">
          <span class="dot" aria-hidden="true" />
          <span>此刻，有 <b>{{ online }}</b> 位炉友正在促膝长谈</span>
        </p>
        <a class="hint" href="#features">往下走走<span class="hint-line" aria-hidden="true"><span /></span></a>
      </div>
    </section>

    <section id="features" class="features">
      <p class="eyebrow">炉边有什么 · BY THE FIRE</p>
      <h2>慢一点，故事才暖得起来。</h2>
      <article v-for="(f, i) in features" :key="f.num" class="feature" :class="{ reverse: i % 2 }">
        <div class="f-head">
          <span class="f-num" aria-hidden="true">{{ f.num }}</span>
          <div>
            <h3 class="f-title">{{ f.title }}</h3>
            <p class="f-en">{{ f.en }}</p>
          </div>
        </div>
        <p class="f-body">{{ f.body }}</p>
      </article>
    </section>

    <section class="closing">
      <div v-if="night" class="closing-glow" aria-hidden="true" />
      <p>炉火正旺，坐下来吧</p>
      <div class="actions">
        <RouterLink class="hearth-btn primary" :to="enter.to">{{ enter.label }}</RouterLink>
      </div>
    </section>

    <footer class="footer">
      <span>© 2026 炉隅 · Lore Nook</span>
      <a v-if="icp" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">{{ icp }}</a>
    </footer>

  </div>
</template>

<style scoped>
.landing { height: 100dvh; overflow-y: auto; scroll-behavior: smooth; }
.hero {
  position: relative; min-height: 100dvh; box-sizing: border-box; overflow: hidden;
  display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 140px 24px 200px; text-align: center;
}
.hero-body { position: relative; display: flex; flex-direction: column; align-items: center; }
.mark { margin-bottom: 56px; }
.tagline { margin: 0; font-size: clamp(19px, 1.7vw, 24px); letter-spacing: 0.38em; padding-left: 0.38em; }
.sub { margin: 20px 0 0; max-width: 30em; font-weight: 300; font-size: 15px; line-height: 2; letter-spacing: 0.14em; color: var(--h-muted); }
.actions { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; margin-top: 52px; }
.bottom { position: absolute; left: 0; right: 0; bottom: 36px; display: flex; flex-direction: column; align-items: center; gap: 28px; }
.presence { margin: 0; display: flex; align-items: center; gap: 10px; font-family: var(--h-sans); font-size: 13px; letter-spacing: 0.16em; color: var(--h-muted); }
.presence b { font-family: var(--h-latin); font-weight: 500; font-size: 17px; letter-spacing: 0.02em; color: var(--h-ink); }
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--h-accent); box-shadow: 0 0 10px 2px var(--h-accent); animation: pulse 2.6s ease-in-out infinite; }
.hint {
  display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--h-muted); text-decoration: none;
  font-family: var(--h-sans); font-size: 12px; letter-spacing: 0.4em; padding-left: 0.4em;
}
.hint:hover { color: var(--h-ink); }
.hint-line { position: relative; width: 1px; height: 44px; background: var(--h-line); overflow: hidden; }
.hint-line span { position: absolute; left: -1px; top: -8px; width: 3px; height: 8px; border-radius: 2px; background: var(--h-accent); animation: fall 2.4s cubic-bezier(0.5, 0, 0.5, 1) infinite; }

.features { position: relative; max-width: 1120px; margin: 0 auto; padding: 160px 32px 80px; }
.eyebrow { margin: 0; font-family: var(--h-sans); font-size: 12px; letter-spacing: 0.45em; color: var(--h-accent); }
h2 { margin: 22px 0 110px; font-weight: 400; font-size: clamp(28px, 3.4vw, 44px); letter-spacing: 0.12em; line-height: 1.5; }
.feature { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 40px 80px; padding: 88px 0; border-top: 1px solid var(--h-line); }
.feature.reverse { flex-direction: row-reverse; }
.f-head { flex: 1 1 300px; display: flex; align-items: baseline; gap: 28px; }
.f-num { font-weight: 300; font-size: 88px; line-height: 1; color: var(--h-accent); opacity: 0.75; }
.f-title { margin: 0; font-weight: 600; font-size: 28px; letter-spacing: 0.2em; }
.f-en { margin: 10px 0 0; font-family: var(--h-latin); font-style: italic; font-size: 19px; letter-spacing: 0.04em; color: var(--h-muted); }
.f-body { flex: 1 1 380px; margin: 0; padding-top: 12px; font-weight: 300; font-size: 17px; line-height: 2.1; letter-spacing: 0.08em; color: var(--h-muted); }

.closing { position: relative; overflow: hidden; padding: 180px 24px 200px; text-align: center; }
.closing p { margin: 0; font-size: clamp(24px, 2.6vw, 34px); letter-spacing: 0.3em; padding-left: 0.3em; }
.closing-glow {
  position: absolute; left: 50%; bottom: -40%; width: 90vw; height: 90%; transform: translateX(-50%); pointer-events: none;
  background: radial-gradient(closest-side, rgb(255 128 44 / 22%), transparent 80%);
}
.footer {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; padding: 28px 40px 36px;
  border-top: 1px solid var(--h-line); font-family: var(--h-sans); font-size: 12px; letter-spacing: 0.14em; color: var(--h-muted);
}
.footer a { color: var(--h-muted); text-decoration: none; }
.footer a:hover { color: var(--h-ink); }

@keyframes pulse { 0%, 100% { opacity: 0.45; } 50% { opacity: 1; } }
@keyframes fall { 0% { top: -8px; opacity: 0; } 20% { opacity: 1; } 100% { top: 44px; opacity: 0; } }
@media (max-width: 640px) {
  .hero { padding: 120px 16px 200px; }
  .mark { margin-bottom: 40px; }
  .tagline { letter-spacing: 0.24em; padding-left: 0.24em; }
  .features { padding: 120px 16px 40px; }
  .feature { padding: 64px 0; }
  .feature.reverse { flex-direction: row; }
  .f-num { font-size: 64px; }
  .footer { padding: 24px 16px 32px; }
}
@media (prefers-reduced-motion: reduce) {
  .landing { scroll-behavior: auto; }
  .dot, .hint-line span { animation: none; }
}
</style>
