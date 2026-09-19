<script setup lang="ts">
import {
  BookOpen,
  ChartColumn,
  Megaphone,
  MessagesSquare
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

const links = [
  {
    id: 'teacher-course-publish',
    to: '/teacher/courses',
    label: '课程管理',
    icon: BookOpen
  },
  {
    id: 'teacher-announcement',
    to: '/teacher/announcements',
    label: '教学公告',
    icon: Megaphone
  },
  {
    id: 'teacher-interactions',
    to: '/teacher/interactions',
    label: '互动答疑',
    icon: MessagesSquare
  },
  {
    id: 'teacher-dashboard',
    to: '/teacher/dashboard',
    label: '数据看板',
    icon: ChartColumn
  }
] as const
</script>

<template>
  <nav class="teacher-console-nav" aria-label="教师工作台导航">
    <div class="teacher-console-nav__inner">
      <RouterLink
        v-for="link in links"
        :id="link.id"
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
.teacher-console-nav {
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.teacher-console-nav__inner {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 180px));
  gap: 4px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 8px 24px 10px;
}

.teacher-console-nav a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  min-height: 44px;
  padding: 0 12px;
  border-bottom: 2px solid transparent;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-height: 1.2;
  text-decoration: none;
  white-space: nowrap;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.teacher-console-nav a span {
  white-space: nowrap;
}

.teacher-console-nav a:hover,
.teacher-console-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.teacher-console-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 760px) {
  .teacher-console-nav__inner {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 2px;
    padding-inline: 14px;
    overflow-x: clip;
  }

  .teacher-console-nav a {
    flex-direction: column;
    gap: 3px;
    min-height: 58px;
    padding: 6px 2px;
    font-size: 0.78rem;
  }
}
</style>
