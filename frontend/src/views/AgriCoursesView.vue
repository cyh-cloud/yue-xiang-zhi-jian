<script setup lang="ts">
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
</script>

<template>
  <CourseLearningPanel
    direction="agriculture"
    module-code="03"
    title="农业课程"
    description="浏览已上架农业课程，从断点继续学习，并在达到完成进度后参加课后测验。"
    api-prefix="/api/agri-skills"
  >
    <template #nav>
      <AgriSkillsNav />
    </template>
  </CourseLearningPanel>
</template>

<style scoped>
.agri-courses-page {
  min-width: 0;
  overflow-x: clip;
}

@media (max-width: 760px) {
  :deep(.recommendation-list) {
    grid-template-columns: minmax(0, 1fr);
  }

  :deep(.course-card__actions button),
  :deep(.course-card__actions a) {
    flex: 1 1 160px;
  }

  :deep(.quiz-submit) {
    width: 100%;
  }
}
</style>
