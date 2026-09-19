<script setup lang="ts">
import { onMounted } from 'vue'

import TeacherCourseManager from '@/components/TeacherCourseManager.vue'
import { useTeacherConsoleStore } from '@/stores/teacherConsole'

const store = useTeacherConsoleStore()

onMounted(() => {
  void store.loadCourses()
})
</script>

<template>
  <div class="teacher-courses-view">
    <header class="page-heading">
      <span class="ark-data">08 / TEACHER COURSES</span>
      <h1>课程管理</h1>
      <p>创建和维护课程视频，按审核状态提交、下架或重新上架。</p>
    </header>

    <TeacherCourseManager />
  </div>
</template>

<style scoped>
.teacher-courses-view {
  min-width: 0;
  overflow-x: clip;
  background: var(--ark-ink);
}

.page-heading {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 0;
}

.page-heading > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.page-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
  text-wrap: balance;
}

.page-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

@media (max-width: 760px), (orientation: portrait) {
  .page-heading {
    padding: 28px 14px 0;
  }

  .page-heading h1 {
    font-size: 2.25rem;
  }
}
</style>
