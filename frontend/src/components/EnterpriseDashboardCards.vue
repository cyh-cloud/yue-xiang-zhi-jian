<script setup lang="ts">
import { BriefcaseBusiness, FileUser } from 'lucide-vue-next'

import type { EnterpriseDashboard } from '@/api/types'

defineProps<{
  dashboard: EnterpriseDashboard
  loading: boolean
}>()
</script>

<template>
  <div class="enterprise-dashboard-cards" aria-label="企业数据概览">
    <article
      class="enterprise-dashboard-card"
      data-test="active-job-count"
      :aria-busy="loading"
    >
      <span class="enterprise-dashboard-card__icon" aria-hidden="true">
        <BriefcaseBusiness :size="21" />
      </span>
      <div class="enterprise-dashboard-card__copy">
        <span class="enterprise-dashboard-card__label">在招职位</span>
        <strong class="enterprise-dashboard-card__value ark-data">
          {{ loading ? '--' : dashboard.active_job_count }}
        </strong>
        <p>已通过审核且当前未删除的职位</p>
      </div>
    </article>

    <article
      class="enterprise-dashboard-card"
      data-test="received-resume-count"
      :aria-busy="loading"
    >
      <span class="enterprise-dashboard-card__icon" aria-hidden="true">
        <FileUser :size="21" />
      </span>
      <div class="enterprise-dashboard-card__copy">
        <span class="enterprise-dashboard-card__label">收到简历</span>
        <strong class="enterprise-dashboard-card__value ark-data">
          {{ loading ? '--' : dashboard.received_resume_count }}
        </strong>
        <p>当前企业累计收到的唯一申请</p>
      </div>
    </article>
  </div>
</template>

<style scoped>
.enterprise-dashboard-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}

.enterprise-dashboard-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.enterprise-dashboard-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.enterprise-dashboard-card__copy {
  display: grid;
  min-width: 0;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-dashboard-card__label {
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.enterprise-dashboard-card__value {
  margin-top: 2px;
  color: var(--ark-paper);
  font-size: 2.5rem;
  line-height: 1.05;
}

.enterprise-dashboard-card__copy p {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

@media (max-width: 720px) {
  .enterprise-dashboard-cards {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
