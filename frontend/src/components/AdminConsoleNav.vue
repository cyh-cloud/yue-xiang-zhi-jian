<script setup lang="ts">
import {
  ClipboardCheck,
  Files,
  Gauge,
  Gift,
  Library,
  Megaphone,
  MessagesSquare,
  PackageCheck,
  SlidersHorizontal,
  Users
} from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import type { AdminConsoleRole } from '@/api/types'

interface AdminNavLink {
  to: string
  label: string
  icon: typeof Gauge
  testId: string
  superAdminOnly?: boolean
}

const props = defineProps<{
  role: AdminConsoleRole
}>()

const links: AdminNavLink[] = [
  {
    to: '/admin',
    label: '数据看板',
    icon: Gauge,
    testId: 'admin-nav-dashboard'
  },
  {
    to: '/admin/review',
    label: '内容审核',
    icon: ClipboardCheck,
    testId: 'admin-nav-review'
  },
  {
    to: '/admin/moderation',
    label: '评论监管',
    icon: MessagesSquare,
    testId: 'admin-nav-moderation'
  },
  {
    to: '/admin/presets',
    label: '预置内容',
    icon: Library,
    testId: 'admin-nav-presets'
  },
  {
    to: '/admin/rewards',
    label: '奖品管理',
    icon: Gift,
    testId: 'admin-nav-rewards'
  },
  {
    to: '/admin/redemptions',
    label: '兑换履约',
    icon: PackageCheck,
    testId: 'admin-nav-redemptions'
  },
  {
    to: '/admin/accounts',
    label: '账号管理',
    icon: Users,
    testId: 'admin-nav-accounts',
    superAdminOnly: true
  },
  {
    to: '/admin/points-policy',
    label: '积分规则',
    icon: SlidersHorizontal,
    testId: 'admin-nav-points-policy',
    superAdminOnly: true
  },
  {
    to: '/admin/content',
    label: '数据管理',
    icon: Files,
    testId: 'admin-nav-content',
    superAdminOnly: true
  },
  {
    to: '/admin/announcements',
    label: '系统公告',
    icon: Megaphone,
    testId: 'admin-nav-announcements',
    superAdminOnly: true
  }
]

const route = useRoute()
const visibleLinks = computed(() =>
  links.filter(link => !link.superAdminOnly || props.role === 'super_admin')
)

function isActive(to: string): boolean {
  if (to === '/admin') {
    return route.path === '/admin' || route.path.startsWith('/admin/dashboard')
  }
  return route.path === to || route.path.startsWith(`${to}/`)
}
</script>

<template>
  <nav
    class="admin-console-nav"
    aria-label="管理后台导航"
    data-test="admin-console-nav"
  >
    <div class="admin-console-nav__inner">
      <RouterLink
        v-for="link in visibleLinks"
        :key="link.to"
        :to="link.to"
        :data-test="link.testId"
        :class="{ 'is-active': isActive(link.to) }"
      >
        <component :is="link.icon" :size="17" aria-hidden="true" />
        <span>{{ link.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.admin-console-nav {
  min-width: 0;
  overflow-x: clip;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.admin-console-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  min-width: 0;
  margin-inline: auto;
  padding: 8px 24px 10px;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
  scrollbar-color: var(--ark-line-strong) var(--ark-surface-1);
  scrollbar-width: thin;
}

.admin-console-nav a {
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

.admin-console-nav a:hover,
.admin-console-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.admin-console-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 720px) {
  .admin-console-nav__inner {
    padding-inline: 14px;
  }
}
</style>
