<script setup lang="ts">
import { computed, onMounted } from 'vue'

import AppHeader from '@/components/AppHeader.vue'
import AuthDialog from '@/components/AuthDialog.vue'
import HomeHero from '@/components/HomeHero.vue'
import ModuleSection from '@/components/ModuleSection.vue'
import { useAuthStore } from '@/stores/auth'
import { useHomeStore } from '@/stores/home'
import type { ModuleId } from '@/api/types'

const home = useHomeStore()
const auth = useAuthStore()

const generatedAt = computed(() => {
  const date = new Date(home.snapshot.generatedAt)
  if (Number.isNaN(date.getTime())) {
    return '未记录'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
})

const sourceText = computed(() => {
  if (home.loading) {
    return '正在同步 Flask 数据'
  }
  if (home.snapshot.source === 'live') {
    return 'Flask 数据已连接'
  }
  if (home.snapshot.source === 'mixed') {
    return 'Flask 与示例数据混合'
  }
  return '接口未连接或为空，已使用示例数据'
})

function scrollBehavior(): ScrollBehavior {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
}

function goToModule(id: ModuleId) {
  home.selectModule(id)
  document.getElementById(`module-${id}`)?.scrollIntoView({
    behavior: scrollBehavior(),
    block: 'start'
  })
}

function activateModule(id: ModuleId) {
  home.selectModule(id)
  document.getElementById('home')?.scrollIntoView({
    behavior: scrollBehavior(),
    block: 'start'
  })
}

onMounted(() => {
  void home.load()
})
</script>

<template>
  <div id="home" class="home">
    <AppHeader
      :source="home.snapshot.source"
      :loading="home.loading"
      :user-name="auth.user?.name"
      @refresh="home.load(true)"
      @open-auth="auth.openDialog"
      @logout="auth.logout"
    />

    <HomeHero
      :modules="home.modules"
      :active-module-id="home.activeModuleId"
      :source="home.snapshot.source"
      :loading="home.loading"
      @select="goToModule"
    />

    <div class="status-strip" role="status" aria-live="polite">
      <div class="status-copy">
        <span class="source-dot" :data-source="home.snapshot.source" aria-hidden="true"></span>
        <strong>{{ sourceText }}</strong>
        <span v-if="auth.notice">{{ auth.notice }}</span>
        <span class="ark-data">更新 {{ generatedAt }}</span>
      </div>
      <button type="button" :disabled="home.loading" @click="home.load(true)">
        重新同步
      </button>
    </div>

    <main :aria-busy="home.loading" class="module-list">
      <ModuleSection
        v-for="module in home.modules"
        :key="module.id"
        :module="module"
        :active="module.id === home.activeModuleId"
        @activate="activateModule"
      />

      <section class="prototype-note" aria-labelledby="prototype-title">
        <div>
        <h2 id="prototype-title">演示边界</h2>
        <p>
            这是演示原型：Vue 3 前端通过内部 API adapter 调用 Flask，接口失败或返回空时使用前端示例数据。
            示例中的岗位、政策、课程与指标不代表生产承诺。
          </p>
        </div>
        <dl>
          <div>
            <dt>前端</dt>
            <dd>Vue 3 · Vite · Pinia</dd>
          </div>
          <div>
            <dt>后端</dt>
            <dd>Flask API</dd>
          </div>
          <div>
            <dt>兼容层</dt>
            <dd>frontend/src/api/adapters</dd>
          </div>
        </dl>
      </section>
    </main>

    <footer class="site-footer">
      <div>
        <strong>粤乡智匠</strong>
        <span>农村学员学习与就业原型</span>
      </div>
      <span>示例数据仅用于原型 · 不代表生产承诺</span>
    </footer>

    <AuthDialog />
  </div>
</template>

<style scoped>
.home {
  min-width: 320px;
  background: var(--ark-ink);
}

.status-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: min(100%, var(--ark-shell-max));
  margin: 0 auto;
  padding: 10px 24px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.status-copy {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.79rem;
}

.status-copy strong {
  color: var(--ark-paper);
  font-weight: 500;
}

.source-dot {
  width: 7px;
  height: 7px;
  background: var(--ark-signal);
}

.source-dot[data-source="live"] {
  background: var(--ark-state);
}

.status-strip button {
  flex: 0 0 auto;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.79rem;
}

.status-strip button:hover:not(:disabled),
.status-strip button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
  background: rgb(24 209 255 / 0.1);
}

.module-list {
  display: block;
}

.prototype-note {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: 26px;
  width: min(100%, var(--ark-shell-max));
  margin: 0 auto;
  padding: 54px 24px 68px;
  border-top: 1px solid var(--ark-line);
}

.prototype-note h2 {
  margin: 0;
  font-size: 1.75rem;
  line-height: 1.2;
}

.prototype-note p {
  max-width: 72ch;
  margin: 14px 0 0;
  color: #c4cdcf;
  font-size: 0.94rem;
  line-height: 1.75;
}

.prototype-note dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.prototype-note dl div {
  min-height: 92px;
  padding: 12px;
  background: var(--ark-surface-1);
}

.prototype-note dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.prototype-note dd {
  margin: 7px 0 0;
  font-size: 0.92rem;
  line-height: 1.45;
}

.site-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 24px 24px;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.site-footer > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.site-footer strong {
  color: var(--ark-paper);
}

@media (max-width: 900px) {
  .prototype-note {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 700px) {
  .status-strip {
    align-items: stretch;
    flex-direction: column;
    padding-inline: 14px;
  }

  .status-strip button {
    width: 100%;
  }

  .prototype-note,
  .site-footer {
    padding-inline: 14px;
  }

  .prototype-note dl,
  .site-footer {
    grid-template-columns: minmax(0, 1fr);
  }

  .prototype-note dl {
    grid-template-areas: unset;
  }

  .site-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
