<script setup lang="ts">
import { FileText, RefreshCw, Sparkles } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { useTeacherConsoleStore } from '@/stores/teacherConsole'

const store = useTeacherConsoleStore()
const dashboardError = ref('')
const reportError = ref('')
const selectedReportId = ref('')

const directionGroups = [
  { key: 'agriculture', label: '农业方向' },
  { key: 'ecommerce', label: '电商方向' },
  { key: 'handcraft', label: '手工方向' },
  { key: 'comprehensive', label: '综合方向' }
] as const

const reportHistory = computed(() =>
  Array.isArray(store.reports) ? store.reports : []
)

const selectedReport = computed(
  () =>
    reportHistory.value.find(
      report => report.report_id === selectedReportId.value
    ) ?? null
)

function formatPercent(value: number, fractionDigits: number): string {
  return `${value.toFixed(fractionDigits).replace(/\.0$/, '')}%`
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

async function loadDashboard() {
  dashboardError.value = ''
  try {
    await store.loadDashboard()
  } catch {
    dashboardError.value = store.error || '教师看板加载失败'
  }
}

async function generateReport() {
  reportError.value = ''
  try {
    const report = await store.generateReport()
    selectedReportId.value = report.report_id
  } catch {
    reportError.value = store.error || '学情报告生成失败'
  }
}

async function loadReports() {
  reportError.value = ''
  try {
    const reports = await store.loadReports()
    selectedReportId.value = reports[0]?.report_id ?? ''
  } catch {
    reportError.value = store.error || '学情报告加载失败'
  }
}

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <div class="teacher-dashboard-view">
    <header class="page-heading">
      <span class="ark-data">08 / TEACHER DASHBOARD</span>
      <h1>数据看板</h1>
      <p>查看平台聚合学习数据，生成并回看不含学员身份信息的学情报告。</p>
    </header>

    <main class="dashboard-workspace">
      <p v-if="dashboardError" class="action-error" role="alert">
        {{ dashboardError }}
      </p>

      <section
        v-if="store.dashboard"
        class="metric-grid"
        aria-label="学习数据总览"
      >
        <article data-test="student-total">
          <span>学员总数</span>
          <strong>{{ store.dashboard.student_total }}</strong>
        </article>
        <article data-test="average-progress">
          <span>平均进度</span>
          <strong>{{ store.dashboard.average_progress.toFixed(1) }}%</strong>
        </article>
        <article data-test="completion-rate">
          <span>完成率</span>
          <strong>{{ formatPercent(store.dashboard.completion_rate, 1) }}</strong>
        </article>
        <article data-test="quiz-attempts">
          <span>测验作答人次</span>
          <strong>{{ store.dashboard.quiz_attempt_count }}</strong>
        </article>
        <article data-test="quiz-average-score">
          <span>测验平均分</span>
          <strong>{{ store.dashboard.quiz_average_score.toFixed(1) }}</strong>
        </article>
      </section>

      <section
        v-if="store.dashboard"
        class="direction-section"
        aria-labelledby="direction-title"
      >
        <header class="section-heading">
          <div>
            <span class="ark-data">DIRECTION COMPARISON</span>
            <h2 id="direction-title">方向分组</h2>
          </div>
          <span>4 个方向</span>
        </header>

        <div class="direction-grid">
          <article
            v-for="direction in directionGroups"
            :key="direction.key"
            :data-test="`direction-${direction.key}`"
          >
            <strong>{{ direction.label }}</strong>
            <dl>
              <div>
                <dt>学员</dt>
                <dd>
                  {{ store.dashboard.directions[direction.key].student_count }} 人
                </dd>
              </div>
              <div>
                <dt>平均进度</dt>
                <dd>
                  {{
                    formatPercent(
                      store.dashboard.directions[direction.key]
                        .average_progress,
                      1
                    )
                  }}
                </dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section
        v-if="store.dashboard"
        class="report-section"
        aria-labelledby="report-title"
      >
        <header class="report-heading">
          <div>
            <span class="ark-data">AI LEARNING REPORT</span>
            <h2 id="report-title">学情报告</h2>
            <p>报告只使用聚合统计，不包含学员身份或可下钻的个人明细。</p>
          </div>
          <button
            type="button"
            data-test="generate-report"
            :disabled="store.reportLoading"
            @click="generateReport"
          >
            <Sparkles :size="17" aria-hidden="true" />
            {{ store.reportLoading ? '正在生成' : '生成学情报告' }}
          </button>
        </header>

        <p v-if="reportError" class="action-error" role="alert">
          {{ reportError }}
        </p>

        <div class="report-workspace">
          <aside class="report-history" aria-labelledby="report-history-title">
            <header>
              <FileText :size="17" aria-hidden="true" />
              <h3 id="report-history-title">报告历史</h3>
              <span>{{ reportHistory.length }} 份</span>
              <button
                type="button"
                data-test="refresh-reports"
                :disabled="store.loading"
                @click="loadReports"
              >
                <RefreshCw
                  :size="15"
                  :class="{ spinning: store.loading }"
                  aria-hidden="true"
                />
                刷新
              </button>
            </header>
            <div v-if="reportHistory.length" class="report-history-list">
              <button
                v-for="report in reportHistory"
                :key="report.report_id"
                type="button"
                data-test="report-history-item"
                :aria-pressed="selectedReportId === report.report_id"
                :class="{ active: selectedReportId === report.report_id }"
                @click="selectedReportId = report.report_id"
              >
                <strong>学情报告</strong>
                <time :datetime="report.created_at">
                  {{ formatTimestamp(report.created_at) }}
                </time>
              </button>
            </div>
            <p v-else>暂无已保存报告</p>
          </aside>

          <article
            v-if="selectedReport"
            class="report-detail"
            data-test="report-detail"
          >
            <header>
              <div>
                <span class="ark-data">SAVED REPORT</span>
                <h3>报告详情</h3>
              </div>
              <time :datetime="selectedReport.created_at">
                生成于 {{ formatTimestamp(selectedReport.created_at) }}
              </time>
            </header>

            <section data-test="report-section-progress">
              <h4>进度分析</h4>
              <p>{{ selectedReport.sections.progress_analysis }}</p>
            </section>
            <section data-test="report-section-direction">
              <h4>方向对比</h4>
              <p>{{ selectedReport.sections.direction_comparison }}</p>
            </section>
            <section data-test="report-section-risk">
              <h4>风险预警</h4>
              <p>{{ selectedReport.sections.risk_warning }}</p>
            </section>
          </article>

          <div v-else class="report-detail-empty">
            <FileText :size="24" aria-hidden="true" />
            <strong>选择一份报告查看详情</strong>
            <p>生成报告后，进度分析、方向对比和风险预警会显示在这里。</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.teacher-dashboard-view {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.page-heading,
.dashboard-workspace {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding-inline: 24px;
}

.page-heading {
  padding-top: 40px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.page-heading > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.page-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.page-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.dashboard-workspace {
  padding-top: 22px;
  padding-bottom: 72px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.metric-grid article {
  display: grid;
  min-width: 0;
  min-height: 126px;
  align-content: space-between;
  gap: 18px;
  padding: 17px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.metric-grid span {
  color: var(--ark-muted);
  font-size: 0.8rem;
  font-weight: 700;
  line-break: strict;
  text-wrap: pretty;
  word-break: keep-all;
}

.metric-grid strong {
  color: var(--ark-paper);
  font-size: 2rem;
  line-height: 1;
  overflow-wrap: normal;
  word-break: keep-all;
}

.direction-section {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 12px;
}

.section-heading > div {
  min-width: 0;
}

.section-heading > div > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.section-heading h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
  line-break: strict;
  word-break: keep-all;
}

.section-heading > span {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.direction-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.direction-grid article {
  display: grid;
  min-width: 0;
  gap: 14px;
  padding: 17px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.direction-grid article > strong {
  line-break: strict;
  text-wrap: pretty;
  word-break: keep-all;
}

.direction-grid dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.direction-grid dl > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  padding-top: 8px;
  border-top: 1px solid var(--ark-line);
}

.direction-grid dt {
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  word-break: keep-all;
}

.direction-grid dd {
  margin: 0;
  font-weight: 700;
  line-break: strict;
  white-space: nowrap;
}

.report-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--ark-line-strong);
}

.report-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
}

.report-heading > div {
  min-width: 0;
}

.report-heading > div > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.report-heading h2 {
  margin: 3px 0 0;
  font-size: 1.25rem;
  line-break: strict;
  word-break: keep-all;
}

.report-heading p {
  max-width: 58ch;
  margin: 7px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.report-heading button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-weight: 700;
  white-space: normal;
}

.report-heading button:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.report-workspace {
  display: grid;
  grid-template-columns: minmax(220px, 0.72fr) minmax(0, 1.5fr);
  gap: 12px;
  align-items: start;
}

.report-history,
.report-detail,
.report-detail-empty {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.report-history > header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 52px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.report-history > header svg {
  color: var(--ark-signal);
}

.report-history h3 {
  margin: 0;
  font-size: 0.92rem;
}

.report-history > header span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.report-history > header button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-height: 32px;
  padding: 0 8px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.72rem;
  white-space: nowrap;
}

.report-history > header button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.report-history-list {
  display: grid;
}

.report-history-list button {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: 13px 14px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
  border-left: 3px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-align: left;
}

.report-history-list button:last-child {
  border-bottom: 0;
}

.report-history-list button:hover,
.report-history-list button.active {
  border-left-color: var(--ark-signal);
  background: var(--ark-surface-1);
}

.report-history-list strong {
  line-break: strict;
  word-break: keep-all;
}

.report-history-list time {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.report-history > p {
  min-height: 118px;
  margin: 0;
  padding: 24px 14px;
  color: var(--ark-muted);
  text-align: center;
}

.report-detail {
  display: grid;
}

.report-detail > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.report-detail > header > div {
  min-width: 0;
}

.report-detail > header span {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.report-detail h3 {
  margin: 2px 0 0;
  font-size: 1rem;
  line-break: strict;
  word-break: keep-all;
}

.report-detail time {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  text-align: right;
  word-break: keep-all;
}

.report-detail > section {
  padding: 15px 16px;
  border-bottom: 1px solid var(--ark-line);
  border-left: 3px solid var(--ark-signal);
}

.report-detail > section:nth-of-type(2) {
  border-left-color: var(--ark-state);
}

.report-detail > section:last-child {
  border-bottom: 0;
}

.report-detail h4 {
  margin: 0;
  font-size: 0.88rem;
  line-break: strict;
  word-break: keep-all;
}

.report-detail section p {
  margin: 6px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.report-detail-empty {
  display: grid;
  place-items: center;
  min-height: 250px;
  padding: 28px 20px;
  color: var(--ark-muted);
  text-align: center;
}

.report-detail-empty svg {
  color: var(--ark-signal);
}

.report-detail-empty strong {
  margin-top: 9px;
  color: var(--ark-paper);
  line-break: strict;
  text-wrap: pretty;
  word-break: keep-all;
}

.report-detail-empty p {
  max-width: 42ch;
  margin: 6px 0 0;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.action-error {
  margin: 0 0 16px;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  overflow-wrap: break-word;
  word-break: normal;
}

@media (max-width: 860px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .direction-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .report-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .page-heading,
  .dashboard-workspace {
    padding-inline: 14px;
  }

  .page-heading {
    padding-top: 28px;
  }

  .page-heading h1 {
    font-size: 2.25rem;
  }

  .metric-grid article {
    min-height: 112px;
    padding: 14px;
  }

  .direction-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-heading {
    align-items: stretch;
    flex-direction: column;
    gap: 14px;
  }

  .report-heading button {
    width: 100%;
  }

  .report-detail > header {
    flex-direction: column;
  }

  .report-detail time {
    text-align: left;
  }
}
</style>
