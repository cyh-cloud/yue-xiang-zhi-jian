<script setup lang="ts">
import {
  BarChart3,
  BriefcaseBusiness,
  Newspaper,
  RefreshCw,
  ScrollText,
  ShieldAlert
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'

import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

interface MetricCard {
  key: string
  testId: string
  label: string
  value: number | null | undefined
}

const store = useGovernmentConsoleStore()

const employmentCards = computed<MetricCard[]>(() => [
  {
    key: 'active_job_count',
    testId: 'active-job-count',
    label: '在招岗位数',
    value: store.dashboard?.employment.active_job_count
  },
  {
    key: 'cumulative_application_count',
    testId: 'cumulative-application-count',
    label: '累计投递量',
    value: store.dashboard?.employment.cumulative_application_count
  }
])

const policyCards = computed<MetricCard[]>(() => [
  {
    key: 'active_count',
    testId: 'policy-active',
    label: '在架政策数',
    value: store.dashboard?.policy.active_count
  },
  {
    key: 'unpublished_count',
    testId: 'policy-unpublished',
    label: '下架政策数',
    value: store.dashboard?.policy.unpublished_count
  },
  {
    key: 'view_count',
    testId: 'policy-views',
    label: '政策累计点击浏览量',
    value: store.dashboard?.policy.view_count
  }
])

const newsCards = computed<MetricCard[]>(() => [
  {
    key: 'total_count',
    testId: 'news-total',
    label: '新闻总数',
    value: store.dashboard?.news.total_count
  },
  {
    key: 'view_count',
    testId: 'news-views',
    label: '新闻累计点击浏览量',
    value: store.dashboard?.news.view_count
  }
])

const employmentAvailable = computed(
  () => store.dashboard?.employment.available === true
)

function metricValue(value: number | null | undefined): string {
  return value === null || value === undefined ? '--' : String(value)
}

onMounted(() => {
  void store.loadDashboard()
})
</script>

<template>
  <div
    class="government-dashboard-page"
    data-test="government-dashboard"
  >
    <GovernmentConsoleNav />

    <main
      class="government-dashboard"
      data-ark-theme="ark"
      data-ark-depth="maximal"
    >
      <header class="dashboard-hero">
        <div class="dashboard-hero__identity">
          <BarChart3 :size="25" aria-hidden="true" />
          <div>
            <h1>数据看板</h1>
            <p>就业、政策与新闻业务指标</p>
          </div>
        </div>
      </header>

      <div
        v-if="store.error"
        class="dashboard-error"
        data-test="dashboard-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.error }}</span>
        <button
          type="button"
          data-test="dashboard-retry"
          @click="store.loadDashboard"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <div
        v-if="store.loading && !store.dashboard"
        class="dashboard-loading"
        data-test="dashboard-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载数据
      </div>

      <p
        v-else-if="!store.dashboard"
        class="dashboard-empty"
        data-test="dashboard-empty"
      >
        暂无可展示数据
      </p>

      <div v-else class="dashboard-groups">
        <section
          class="dashboard-group"
          aria-labelledby="dashboard-employment-title"
        >
          <header class="dashboard-group__heading">
            <BriefcaseBusiness :size="18" aria-hidden="true" />
            <h2 id="dashboard-employment-title">就业</h2>
          </header>

          <dl class="dashboard-metrics">
            <div
              v-for="card in employmentCards"
              :key="card.key"
              class="dashboard-metric"
              :data-test="`metric-${card.testId}`"
            >
              <dt data-test="metric-label">{{ card.label }}</dt>
              <dd class="ark-data">{{ metricValue(card.value) }}</dd>
              <p
                v-if="!employmentAvailable"
                data-test="employment-unavailable"
              >
                就业数据暂不可用
              </p>
            </div>
          </dl>
        </section>

        <section
          class="dashboard-group"
          aria-labelledby="dashboard-policy-title"
        >
          <header class="dashboard-group__heading">
            <ScrollText :size="18" aria-hidden="true" />
            <h2 id="dashboard-policy-title">政策</h2>
          </header>

          <dl class="dashboard-metrics">
            <div
              v-for="card in policyCards"
              :key="card.key"
              class="dashboard-metric"
              :data-test="`metric-${card.testId}`"
            >
              <dt data-test="metric-label">{{ card.label }}</dt>
              <dd class="ark-data">{{ metricValue(card.value) }}</dd>
            </div>
          </dl>
        </section>

        <section
          class="dashboard-group"
          aria-labelledby="dashboard-news-title"
        >
          <header class="dashboard-group__heading">
            <Newspaper :size="18" aria-hidden="true" />
            <h2 id="dashboard-news-title">新闻</h2>
          </header>

          <dl class="dashboard-metrics">
            <div
              v-for="card in newsCards"
              :key="card.key"
              class="dashboard-metric"
              :data-test="`metric-${card.testId}`"
            >
              <dt data-test="metric-label">{{ card.label }}</dt>
              <dd class="ark-data">{{ metricValue(card.value) }}</dd>
            </div>
          </dl>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.government-dashboard-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.government-dashboard {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color: var(--ark-paper);
}

.dashboard-hero {
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dashboard-hero__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 26px;
}

.dashboard-hero__identity > svg {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--ark-signal);
}

.dashboard-hero__identity > div {
  min-width: 0;
}

.dashboard-hero__identity h1 {
  margin: 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.dashboard-hero__identity p {
  max-width: 62ch;
  margin: 10px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.dashboard-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.dashboard-error > span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  margin-left: auto;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.dashboard-error button:hover,
.dashboard-error button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.dashboard-loading,
.dashboard-empty {
  display: flex;
  min-height: 200px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 18px 0 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.dashboard-group {
  min-width: 0;
  background: var(--ark-surface-0);
}

.dashboard-group__heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  color: var(--ark-signal);
}

.dashboard-group__heading svg {
  flex: 0 0 auto;
}

.dashboard-group__heading h2 {
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.92rem;
  line-height: 1.35;
  text-wrap: balance;
}

.dashboard-metrics {
  min-width: 0;
  margin: 0;
}

.dashboard-metric {
  min-width: 0;
  min-height: 96px;
  padding: 16px;
  border-bottom: 1px solid var(--ark-line);
}

.dashboard-metric:last-child {
  border-bottom: 0;
}

.dashboard-metric dt {
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: nowrap;
  word-break: keep-all;
}

.dashboard-metric dd {
  margin: 7px 0 0;
  color: var(--ark-paper);
  font-size: 1.95rem;
  line-height: 1;
}

.dashboard-metric p {
  margin: 7px 0 0;
  color: var(--ark-signal);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.government-dashboard :is(button, a):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .government-dashboard {
    padding: 28px 14px 48px;
  }

  .dashboard-hero__identity {
    padding: 20px 16px;
  }

  .dashboard-hero__identity h1 {
    font-size: 2.15rem;
  }

  .dashboard-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-error button {
    width: 100%;
    margin-left: 0;
  }

  .dashboard-groups {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
