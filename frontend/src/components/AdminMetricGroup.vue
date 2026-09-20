<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  metrics: Record<string, number>
  labels?: Record<string, string>
}>()

function metricTestId(key: string): string {
  return `admin-metric-${key
    .replace(/[._]+/g, '-')
    .replace(/[^a-zA-Z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()}`
}

function displayValue(value: number): string {
  return value.toLocaleString('zh-CN')
}

const entries = computed(() => Object.entries(props.metrics))
</script>

<template>
  <section
    class="admin-metric-group"
    aria-label="管理后台指标"
    data-test="admin-metric-group"
  >
    <article
      v-for="[key, value] in entries"
      :key="key"
      class="admin-metric-group__item"
      :data-test="metricTestId(key)"
      :data-metric-key="key"
    >
      <span class="admin-metric-group__label">
        {{ labels?.[key] ?? key }}
      </span>
      <strong class="admin-metric-group__value">
        {{ displayValue(value) }}
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

</style>
