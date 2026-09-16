<script setup lang="ts">
import {
  BookOpen,
  Home,
  MessagesSquare,
  Mic2,
  PenLine,
  Radio,
  Store
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  { to: '/student/ecommerce-training', label: '模块首页', icon: Home },
  {
    to: '/student/ecommerce-training/live-script',
    label: '直播话术',
    icon: Radio
  },
  {
    to: '/student/ecommerce-training/simulation',
    label: '模拟训练',
    icon: Mic2
  },
  {
    to: '/student/ecommerce-training/copy-training',
    label: '文案训练',
    icon: PenLine
  },
  {
    to: '/student/ecommerce-training/store-guidance',
    label: '店铺装修',
    icon: Store
  },
  {
    to: '/student/ecommerce-training/customer-service',
    label: '客服模拟',
    icon: MessagesSquare
  },
  {
    to: '/student/ecommerce-training/courses',
    label: '电商课程',
    icon: BookOpen
  }
] as const
</script>

<template>
  <nav class="ecommerce-training-nav" aria-label="电商运营实训导航">
    <div class="ecommerce-training-nav__inner">
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
.ecommerce-training-nav {
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.ecommerce-training-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 8px 24px;
  overflow-x: auto;
  scrollbar-width: none;
}

.ecommerce-training-nav__inner::-webkit-scrollbar {
  display: none;
}

.ecommerce-training-nav a {
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

.ecommerce-training-nav a:hover,
.ecommerce-training-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.ecommerce-training-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .ecommerce-training-nav__inner {
    padding-inline: 14px;
  }
}
</style>
