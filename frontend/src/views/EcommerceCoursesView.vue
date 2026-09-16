<script setup lang="ts">
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
</script>

<template>
  <CourseLearningPanel
    direction="ecommerce"
    module-code="04"
    title="电商课程"
    description="浏览电商方向已上架课程，按兴趣和学习行为获取推荐并完成 AI 课后测验。"
    api-prefix="/api/ecommerce-training"
  >
    <template #nav>
      <EcommerceTrainingNav />
    </template>
  </CourseLearningPanel>
</template>
