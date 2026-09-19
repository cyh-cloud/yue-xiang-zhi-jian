<script setup lang="ts">
import type { EffectiveApplicationStatus } from '@/api/types'

const props = defineProps<{
  status: EffectiveApplicationStatus
  positionClosed: boolean
}>()

const labels = {
  pending: '待处理',
  viewed: '已查看',
  intent: '意向沟通',
  unsuitable: '不合适',
  closed: '岗位已关闭'
} as const
</script>

<template>
  <span class="application-status-badge">
    <span
      class="application-status-badge__status"
      :data-status="props.status"
      data-test="effective-status-badge"
    >
      {{ labels[props.status] }}
    </span>
    <span
      v-if="props.positionClosed && props.status !== 'closed'"
      class="application-status-badge__closed"
      data-test="position-closed-badge"
    >
      岗位已关闭
    </span>
  </span>
</template>

<style scoped>
.application-status-badge {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.application-status-badge__status,
.application-status-badge__closed {
  display: inline-flex;
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

.application-status-badge__status[data-status="intent"] {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-status-badge__status[data-status="unsuitable"] {
  color: var(--ark-muted);
}

.application-status-badge__closed {
  border-color: var(--ark-line-strong);
  color: var(--ark-state);
}
</style>
