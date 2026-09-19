<script setup lang="ts">
import {
  ArrowRight,
  Languages,
  Newspaper,
  ScrollText,
  Trophy
} from 'lucide-vue-next'
import { RouterLink, useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const entries = [
  {
    to: '/student/local-resources/dialect',
    title: '方言助手',
    description: '使用粤语、客家话或潮汕话完成语音问答。',
    icon: Languages
  },
  {
    to: '/student/local-resources/cases',
    title: '成功案例',
    description: '阅读本地创业案例的背景、历程与经验启示。',
    icon: Trophy
  },
  {
    to: '/student/local-resources/policies',
    title: '政策',
    description: '按类别浏览政策、管理订阅并查看详情。',
    icon: ScrollText
  },
  {
    to: '/student/local-resources/news',
    title: '新闻',
    description: '查看新闻、灾害预警与政策更新。',
    icon: Newspaper
  }
] as const

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="local-resources-home">
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <LocalResourcesNav />

    <main class="local-resources-home__main">
      <header class="local-resources-home__heading">
        <h1>本土资源</h1>
        <p>集中查找广东本地方言、创业案例、政策与新闻。</p>
      </header>

      <section aria-labelledby="local-resources-entries-title">
        <h2 id="local-resources-entries-title">功能入口</h2>

        <nav class="local-resources-home__entries" aria-label="本土资源功能入口">
          <RouterLink
            v-for="entry in entries"
            :key="entry.to"
            class="local-resources-home__entry"
            :to="entry.to"
          >
            <component :is="entry.icon" :size="24" aria-hidden="true" />
            <span class="local-resources-home__entry-copy">
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
            </span>
            <ArrowRight :size="18" aria-hidden="true" />
          </RouterLink>
        </nav>
      </section>
    </main>
  </div>
</template>

<style scoped>
.local-resources-home {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
}

.local-resources-home__main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 48px 24px 72px;
}

.local-resources-home__heading {
  padding-bottom: 28px;
}

.local-resources-home__heading h1 {
  margin: 0;
  font-size: 2.8rem;
  line-height: 1.05;
}

.local-resources-home__heading p {
  max-width: 62ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resources-home h2 {
  margin: 0;
  font-size: 1.1rem;
}

.local-resources-home__entries {
  display: grid;
  margin-top: 12px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resources-home__entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  min-height: 104px;
  padding: 18px 14px;
  border-bottom: 1px solid var(--ark-line);
  color: var(--ark-paper);
  text-decoration: none;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.local-resources-home__entry > svg:first-child {
  color: var(--ark-signal);
}

.local-resources-home__entry > svg:last-child {
  color: var(--ark-muted);
}

.local-resources-home__entry:hover,
.local-resources-home__entry:focus-visible {
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.local-resources-home__entry-copy {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.local-resources-home__entry-copy strong {
  font-size: 1rem;
}

.local-resources-home__entry-copy small {
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

@media (max-width: 640px) {
  .local-resources-home__main {
    padding: 32px 14px 48px;
  }

  .local-resources-home__heading h1 {
    font-size: 2.2rem;
  }

  .local-resources-home__entry {
    gap: 12px;
    min-height: 96px;
    padding-inline: 4px;
  }
}
</style>
