<script setup lang="ts">
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
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
