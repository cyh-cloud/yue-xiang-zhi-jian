<script setup lang="ts">
import { computed } from 'vue'

import type {
  AdminMetricRecord,
  AdminMetricValue
} from '@/api/types'

interface MetricEntry {
  key: string
  value: AdminMetricValue
}

const props = defineProps<{
  metrics: AdminMetricRecord
  labels?: Record<string, string>
}>()

function isMetricValue(
  value: AdminMetricValue | AdminMetricRecord
): value is AdminMetricValue {
  if (typeof value === 'number') {
    return true
  }
  return (
    'available' in value &&
    'value' in value &&
    typeof value.available === 'boolean'
  )
}

function flattenMetrics(
  metrics: AdminMetricRecord,
  prefix = ''
): MetricEntry[] {
  return Object.entries(metrics).flatMap(([key, value]) => {
    const metricKey = prefix ? `${prefix}.${key}` : key
    return isMetricValue(value)
      ? [{ key: metricKey, value }]
      : flattenMetrics(value, metricKey)
  })
}

function metricTestId(key: string): string {
  return `admin-metric-${key
    .replace(/[._]+/g, '-')
    .replace(/[^a-zA-Z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()}`
}

function displayValue(value: AdminMetricValue): string {
  if (typeof value === 'number') {
    return value.toLocaleString('zh-CN')
  }
  if (!value.available || value.value === null) {
    return '不可用'
  }
  return value.value.toLocaleString('zh-CN')
}

function available(value: AdminMetricValue): boolean {
  return typeof value === 'number' || value.available
}

const entries = computed(() => flattenMetrics(props.metrics))
</script>

<template>
  <section
    class="admin-metric-group"
    aria-label="管理后台指标"
    data-test="admin-metric-group"
  >
    <article
      v-for="entry in entries"
      :key="entry.key"
      class="admin-metric-group__item"
      :data-test="metricTestId(entry.key)"
      :data-metric-key="entry.key"
      :data-available="available(entry.value)"
    >
      <span class="admin-metric-group__label">
        {{ labels?.[entry.key] ?? entry.key }}
      </span>
      <strong class="admin-metric-group__value">
        {{ displayValue(entry.value) }}
      </strong>
    </article>
  </section>
</template>

<style scoped>
.admin-metric-group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: 1px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.admin-metric-group__item {
  display: grid;
  gap: 8px;
  min-width: 0;
  min-height: 104px;
  align-content: space-between;
  padding: 16px;
  background: var(--ark-surface-0);
}

.admin-metric-group__label {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.admin-metric-group__value {
  color: var(--ark-paper);
  font-size: 1.55rem;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

.admin-metric-group__item[data-available="false"] .admin-metric-group__value {
  color: var(--ark-muted);
  font-size: 1rem;
}
</style>
