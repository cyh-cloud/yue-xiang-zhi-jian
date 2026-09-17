<script setup lang="ts">
import { BookOpen, Home } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    to: '/student/handcraft-inheritance',
    label: '技艺学习',
    icon: Home
  },
  {
    to: '/student/handcraft-inheritance/courses',
    label: '手工课程',
    icon: BookOpen
  }
] as const
</script>

<template>
  <nav class="handcraft-nav" aria-label="手工传承导航">
    <div class="handcraft-nav__inner">
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
.handcraft-nav {
  position: relative;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.handcraft-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 8px 24px 10px;
  overflow-x: auto;
  scrollbar-color: var(--ark-line-strong) var(--ark-surface-1);
  scrollbar-width: thin;
}

.handcraft-nav a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 12px;
  border-bottom: 2px solid transparent;
  color: var(--ark-muted);
  font-size: 0.84rem;
  text-decoration: none;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.handcraft-nav a:hover,
.handcraft-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.handcraft-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .handcraft-nav__inner {
    padding-inline: 14px;
  }
}
</style>
