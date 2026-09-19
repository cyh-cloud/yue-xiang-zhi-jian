<script setup lang="ts">
import { computed } from 'vue'

import { segmentChineseText } from '@/utils/chineseTypography'

const props = defineProps<{
  text: string
}>()

const segments = computed(() => segmentChineseText(props.text))
</script>

<template><span
  class="semantic-chinese-text"
  data-test="semantic-chinese-text"
><span
  v-for="segment in segments"
  :key="segment.index"
  class="semantic-chinese-text__segment"
  :class="{ 'is-word': segment.wordLike }"
  :data-segment="segment.wordLike ? 'word' : 'text'"
>{{ segment.text }}</span></span></template>

<style scoped>
.semantic-chinese-text {
  min-width: 0;
}

.semantic-chinese-text__segment.is-word {
  display: inline-block;
  white-space: nowrap;
}
</style>
