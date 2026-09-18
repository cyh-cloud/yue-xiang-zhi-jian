<script setup lang="ts">
import {
  BarChart3,
  Newspaper,
  ScrollText
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    to: '/government/policies',
    label: '政策管理',
    icon: ScrollText
  },
  {
    to: '/government/news',
    label: '新闻管理',
    icon: Newspaper
  },
  {
    to: '/government/dashboard',
    label: '数据看板',
    icon: BarChart3
  }
] as const
</script>

<template>
  <nav class="government-console-nav" aria-label="政务工作台导航">
    <div class="government-console-nav__inner">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        exact-active-class="is-active"
      >
        <component :is="link.icon" :size="17" aria-hidden="true" />
        <span>{{ link.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.government-console-nav {
  position: relative;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.government-console-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  min-width: 0;
  margin-inline: auto;
  padding: 8px 24px 10px;
  overflow-x: auto;
  scrollbar-color: var(--ark-line-strong) var(--ark-surface-1);
  scrollbar-width: thin;
}

.government-console-nav a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 12px;
  border-bottom: 2px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.84rem;
  text-decoration: none;
  white-space: nowrap;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.government-console-nav a:hover,
.government-console-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.government-console-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .government-console-nav__inner {
    padding-inline: 14px;
  }
}
</style>
