<script setup lang="ts">
import { BookOpen, Radio, Sprout, UserRound } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

import PortalShell from '@/components/PortalShell.vue'
</script>

<template>
  <div class="student-portal">
    <PortalShell portal="student" />

    <nav class="student-actions" aria-label="学员可用功能">
      <RouterLink to="/student/courses">
        <BookOpen :size="18" aria-hidden="true" />
        <span>
          <strong>进入课程聚合</strong>
          <small>农业、电商与手工方向</small>
        </span>
      </RouterLink>
      <RouterLink to="/student/profile">
        <UserRound :size="18" aria-hidden="true" />
        <span>
          <strong>编辑个人资料</strong>
          <small>学习方向与兴趣标签</small>
        </span>
      </RouterLink>
      <RouterLink to="/student/agri-skills">
        <Sprout :size="18" aria-hidden="true" />
        <span>
          <strong>进入农业技能</strong>
          <small>农时、问答、诊断与课程</small>
        </span>
      </RouterLink>
      <RouterLink to="/student/ecommerce-training">
        <Radio :size="18" aria-hidden="true" />
        <span>
          <strong>进入电商运营实训</strong>
          <small>直播、文案、装修、客服与课程</small>
        </span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.student-portal {
  min-height: 100svh;
}

.student-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  width: min(calc(100% - 48px), 1180px);
  margin: -48px auto 72px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.student-actions a {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-height: 82px;
  padding: 16px 18px;
  background: rgb(255 255 255 / 0.94);
  text-decoration: none;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.student-actions a:hover,
.student-actions a:focus-visible {
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-signal);
}

.student-actions svg {
  color: var(--ark-signal);
}

.student-actions span {
  display: grid;
  gap: 3px;
}

.student-actions strong {
  font-size: 0.94rem;
}

.student-actions small {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

@media (max-width: 720px) {
  .student-actions {
    grid-template-columns: 1fr;
    width: min(calc(100% - 28px), 1180px);
    margin-top: -32px;
  }
}
</style>
