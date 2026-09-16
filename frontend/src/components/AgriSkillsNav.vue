<script setup lang="ts">
import {
  BookOpen,
  CalendarDays,
  Home,
  MessageCircleQuestion,
  Stethoscope
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    to: '/student/agri-skills',
    label: '模块首页',
    icon: Home
  },
  {
    to: '/student/agri-skills/calendar',
    label: '农时日历',
    icon: CalendarDays
  },
  {
    to: '/student/agri-skills/qa',
    label: '农技问答',
    icon: MessageCircleQuestion
  },
  {
    to: '/student/agri-skills/diagnosis',
    label: '病虫害诊断',
    icon: Stethoscope
  },
  {
    to: '/student/agri-skills/courses',
    label: '农业课程',
    icon: BookOpen
  }
] as const
</script>

<template>
  <nav class="agri-skills-nav" aria-label="农业技能导航">
    <div class="agri-skills-nav__inner">
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
.agri-skills-nav {
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.agri-skills-nav__inner {
  display: flex;
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 8px 24px;
  overflow-x: auto;
  scrollbar-width: none;
}

.agri-skills-nav__inner::-webkit-scrollbar {
  display: none;
}

.agri-skills-nav a {
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

.agri-skills-nav a:hover,
.agri-skills-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.agri-skills-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .agri-skills-nav__inner {
    padding-inline: 14px;
  }
}
</style>
