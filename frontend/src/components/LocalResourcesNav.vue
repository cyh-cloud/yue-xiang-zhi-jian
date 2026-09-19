<script setup lang="ts">
import { Languages, Newspaper, ScrollText, Trophy } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    to: '/student/local-resources/dialect',
    label: '方言助手',
    icon: Languages
  },
  {
    to: '/student/local-resources/cases',
    label: '成功案例',
    icon: Trophy
  },
  {
    to: '/student/local-resources/policies',
    label: '政策',
    icon: ScrollText
  },
  {
    to: '/student/local-resources/news',
    label: '新闻',
    icon: Newspaper
  }
] as const
</script>

<template>
  <nav class="local-resources-nav" aria-label="本土资源导航">
    <div class="local-resources-nav__inner">
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
.local-resources-nav {
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.local-resources-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 8px 24px;
  overflow-x: auto;
  scrollbar-color: var(--ark-line-strong) var(--ark-surface-1);
  scrollbar-width: thin;
}

.local-resources-nav a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 12px;
  border-bottom: 2px solid transparent;
  color: var(--ark-muted);
  font-size: 0.84rem;
  text-decoration: none;
  white-space: nowrap;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.local-resources-nav a:hover,
.local-resources-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.local-resources-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .local-resources-nav__inner {
    padding-inline: 14px;
  }
}
</style>
