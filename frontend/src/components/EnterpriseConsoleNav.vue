<script setup lang="ts">
import {
  BriefcaseBusiness,
  ClipboardList,
  Gauge
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    to: '/enterprise',
    label: '企业看板',
    icon: Gauge,
    testId: 'enterprise-nav-dashboard'
  },
  {
    to: '/enterprise/jobs',
    label: '职位管理',
    icon: BriefcaseBusiness,
    testId: 'enterprise-nav-jobs'
  },
  {
    to: '/enterprise/applications',
    label: '申请处理',
    icon: ClipboardList,
    testId: 'enterprise-nav-applications'
  }
] as const
</script>

<template>
  <nav class="enterprise-console-nav" aria-label="企业工作台导航">
    <div class="enterprise-console-nav__inner">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        :data-test="link.testId"
        exact-active-class="is-active"
      >
        <component :is="link.icon" :size="17" aria-hidden="true" />
        <span>{{ link.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.enterprise-console-nav {
  position: relative;
  min-width: 0;
  overflow-x: clip;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.enterprise-console-nav__inner {
  display: flex;
  gap: 4px;
  min-width: 0;
  padding: 8px 12px 10px;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
  scrollbar-color: var(--ark-line-strong) var(--ark-surface-1);
  scrollbar-width: thin;
}

.enterprise-console-nav a {
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
  white-space: nowrap;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.enterprise-console-nav a:hover,
.enterprise-console-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.enterprise-console-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 720px) {
  .enterprise-console-nav__inner {
    padding-inline: 14px;
  }
}
</style>
