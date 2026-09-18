<script setup lang="ts">
import type { HandcraftCourse } from '@/api/types'
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import HandcraftCoursePlayer from '@/components/HandcraftCoursePlayer.vue'
import type { CourseLearningCourse } from '@/stores/courseLearning'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'

function asHandcraftCourse(course: CourseLearningCourse): HandcraftCourse {
  return course as HandcraftCourse
}
</script>

<template>
  <div
    class="handcraft-courses-page"
    data-test="handcraft-courses-page"
    data-ark-theme="ark"
    data-ark-depth="maximal"
  >
    <CourseLearningPanel
      direction="handcraft"
      module-code="05"
      title="手工课程"
      description="浏览手工方向已上架课程，按兴趣和学习行为获取推荐并完成课后测验。"
      api-prefix="/api/handcraft-inheritance"
    >
      <template #nav>
        <HandcraftInheritanceNav />
      </template>
      <template #course-media="{ course }">
        <HandcraftCoursePlayer :course="asHandcraftCourse(course)" />
      </template>
    </CourseLearningPanel>
  </div>
</template>

<style scoped>
.handcraft-courses-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  width: 100%;
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
}

.handcraft-courses-page > * {
  min-width: 0;
}
</style>
