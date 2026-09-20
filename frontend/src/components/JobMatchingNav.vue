<script setup lang="ts">
import {
  ArrowLeft,
  Bookmark,
  BriefcaseBusiness,
  FileText,
  Send,
  ShieldCheck
} from 'lucide-vue-next'

const links = [
  {
    to: '/student/employment/resume',
    label: '简历维护',
    icon: FileText
  },
  {
    to: '/student/employment/skills',
    label: '我的技能档案',
    icon: ShieldCheck
  },
  {
    to: '/student/employment/jobs',
    label: '岗位浏览',
    icon: BriefcaseBusiness
  },
  {
    to: '/student/employment/applications',
    label: '我的投递',
    icon: Send
  },
  {
    to: '/student/employment/favorites',
    label: '岗位收藏',
    icon: Bookmark
  },
  {
    to: '/student',
    label: '返回学员门户',
    icon: ArrowLeft
  }
] as const
</script>

<template>
  <nav class="job-matching-nav" aria-label="就业对接导航">
    <div class="job-matching-nav__inner">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        :aria-label="link.label"
        exact-active-class="is-active"
      >
        <component :is="link.icon" :size="17" aria-hidden="true" />
        <span>{{ link.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.job-matching-nav {
  min-width: 0;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.job-matching-nav__inner {
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

.job-matching-nav__inner::-webkit-scrollbar {
  height: 6px;
}

.job-matching-nav__inner::-webkit-scrollbar-track {
  background: var(--ark-surface-1);
}

.job-matching-nav__inner::-webkit-scrollbar-thumb {
  background: var(--ark-line-strong);
}

.job-matching-nav a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 12px;
  border-bottom: 2px solid transparent;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  text-decoration: none;
  word-break: keep-all;
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.job-matching-nav a:hover,
.job-matching-nav a:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.job-matching-nav a.is-active {
  border-bottom-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 640px) {
  .job-matching-nav__inner {
    padding-inline: 14px;
  }
}
</style>
