<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'

const governmentEntries = [
  {
    id: 'government-policy-publish',
    label: '政策管理',
    description: '发布与维护面向乡村人才的扶持政策。',
    href: '/government/policies'
  },
  {
    id: 'government-news-publish',
    label: '新闻管理',
    description: '发布地区动态与政务新闻。',
    href: '/government/news'
  },
  {
    id: 'government-dashboard',
    label: '数据看板',
    description: '查看政策、新闻与区域服务数据概览。',
    href: '/government/dashboard'
  },
  {
    id: 'government-messages',
    label: '消息中心',
    description: '查看私信、系统通知与未读消息。',
    href: '/messages'
  }
] as const
</script>

<template>
  <div class="government-portal-page" data-test="government-portal">
    <GovernmentConsoleNav />

    <main
      class="government-portal"
      data-ark-theme="ark"
      data-ark-depth="maximal"
    >
      <header class="government-portal__heading">
        <div>
          <span class="ark-data">GOVERNMENT CONSOLE</span>
          <h1>政务门户</h1>
          <p>政策发布、新闻发布与政务数据功能的集中入口。</p>
        </div>
        <span class="ark-data">政务工作台</span>
      </header>

      <section
        class="government-portal__workspace"
        aria-labelledby="government-workspace-title"
      >
        <header class="government-portal__section-heading">
          <h2 id="government-workspace-title">工作台入口</h2>
          <span class="ark-data">{{ governmentEntries.length }} 个入口</span>
        </header>

        <div class="government-portal__entries">
          <article
            v-for="entry in governmentEntries"
            :id="entry.id"
            :key="entry.id"
            class="government-portal-entry"
            data-test="government-workspace-entry"
          >
            <div class="government-portal-entry__copy">
              <h3>{{ entry.label }}</h3>
              <p>{{ entry.description }}</p>
            </div>
            <RouterLink
              class="government-portal-entry__action"
              :to="entry.href"
            >
              <span>进入</span>
              <ArrowRight :size="15" aria-hidden="true" />
            </RouterLink>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.government-portal-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.government-portal {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.government-portal__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 28px;
  align-items: end;
  min-width: 0;
  padding: 28px 26px;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.government-portal__heading > div {
  min-width: 0;
}

.government-portal__heading > div > span,
.government-portal__heading > span,
.government-portal__section-heading > span {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.government-portal__heading h1 {
  margin: 5px 0 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.government-portal__heading p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.government-portal__workspace {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.government-portal__section-heading {
  display: flex;
  min-width: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.government-portal__section-heading h2 {
  margin: 0;
  font-size: 1.1rem;
  text-wrap: balance;
}

.government-portal__entries {
  display: grid;
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.government-portal-entry {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  min-width: 0;
  min-height: 104px;
  padding: 20px 22px;
  background: var(--ark-surface-0);
}

.government-portal-entry__copy {
  min-width: 0;
}

.government-portal-entry__copy h3 {
  margin: 0;
  font-size: 1.08rem;
  text-wrap: balance;
}

.government-portal-entry__copy p {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.government-portal-entry__action {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-size: 0.76rem;
  text-decoration: none;
  white-space: nowrap;
}

.government-portal-entry__action:hover,
.government-portal-entry__action:focus-visible {
  background: var(--ark-surface-1);
}

@media (max-width: 640px) {
  .government-portal {
    padding: 28px 14px 48px;
  }

  .government-portal__heading {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
    align-items: start;
    padding: 20px 16px;
  }

  .government-portal__heading h1 {
    font-size: 2.15rem;
  }

  .government-portal-entry {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
    padding: 18px;
  }

  .government-portal-entry__action {
    justify-self: start;
  }
}
</style>
