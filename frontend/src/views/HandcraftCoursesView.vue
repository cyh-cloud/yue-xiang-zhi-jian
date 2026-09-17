<script setup lang="ts">
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
</script>

<template>
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
</template>
