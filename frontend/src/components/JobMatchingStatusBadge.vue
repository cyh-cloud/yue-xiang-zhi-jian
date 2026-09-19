<script setup lang="ts">
import { computed } from 'vue'

import type { EffectiveApplicationStatus } from '@/api/types'

const props = defineProps<{
  status: Exclude<EffectiveApplicationStatus, 'closed'>
  effectiveStatus: EffectiveApplicationStatus
  positionClosed: boolean
}>()

const primaryLabel = computed(() =>
  props.effectiveStatus === 'closed'
    ? '岗位已关闭'
    : props.status === 'pending'
      ? '待处理'
      : props.status === 'viewed'
        ? '已查看'
        : props.status === 'intent'
          ? '意向沟通'
          : '不合适'
)
</script>

<template>
  <span class="job-matching-status-badge">
    <span
      class="job-matching-status-badge__primary"
      :data-status="props.effectiveStatus"
      data-test="application-status-label"
    >
      {{ primaryLabel }}
    </span>
    <span
      v-if="props.positionClosed && props.effectiveStatus !== 'closed'"
      class="job-matching-status-badge__closed"
      data-test="application-closed-marker"
    >
      岗位已关闭
    </span>
  </span>
</template>

<style scoped>
.job-matching-status-badge {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.job-matching-status-badge__primary,
.job-matching-status-badge__closed {
  display: inline-flex;
  min-width: 0;
  min-height: 30px;
  max-width: 100%;
  align-items: center;
  justify-content: center;
  padding: 5px 9px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.job-matching-status-badge__primary[data-status="intent"] {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.job-matching-status-badge__primary[data-status="unsuitable"] {
  color: var(--ark-muted);
}

.job-matching-status-badge__primary[data-status="closed"] {
  color: var(--ark-state);
}

.job-matching-status-badge__closed {
  border-color: var(--ark-line-strong);
  color: var(--ark-state);
}

@media (max-width: 720px) {
  .job-matching-status-badge {
    gap: 5px;
  }
}

@media (max-width: 360px) {
  .job-matching-status-badge__primary,
  .job-matching-status-badge__closed {
    padding-inline: 7px;
  }
}
</style>
