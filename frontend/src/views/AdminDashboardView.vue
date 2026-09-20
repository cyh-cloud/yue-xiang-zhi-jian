<script setup lang="ts">
import {
  AlertTriangle,
  Gauge,
  Inbox,
  RefreshCw,
  ShieldAlert
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'

import type {
  AdminDashboardMetric,
  AdminDashboardSnapshot
} from '@/api/types'
import AdminMetricGroup from '@/components/AdminMetricGroup.vue'
import { useAdminConsoleStore } from '@/stores/adminConsole'

type DashboardGroupId = 'review' | 'content' | 'moderation' | 'rewards' | 'users'

interface MetricDefinition {
  key: string
  label: string
  group: DashboardGroupId
  superAdminOnly?: boolean
}

interface GroupView {
  id: DashboardGroupId
  title: string
  note: string
  metrics: Record<string, number>
  labels: Record<string, string>
  unavailable: Array<{ key: string; label: string }>
}

// The flat key mirrors the dashboard DTO path, so a metric tile keeps a
// stable selector even when its source sits one level deeper.
const metricDefinitions: readonly MetricDefinition[] = [
  {
    key: 'pending_review.course_video',
    label: '课程视频待审核',
    group: 'review'
  },
  {
    key: 'pending_review.job_position',
    label: '招聘职位待审核',
    group: 'review'
  },
  {
    key: 'pending_review.handcraft_teaching_video',
    label: '非遗教学视频待审核',
    group: 'review'
  },
  {
    key: 'published_course_count',
    label: '已上架课程',
    group: 'content'
  },
  { key: 'active_job_count', label: '在架职位', group: 'content' },
  {
    key: 'policy_count',
    label: '政策总数',
    group: 'content',
    superAdminOnly: true
  },
  {
    key: 'policy_view_count',
    label: '政策累计浏览',
    group: 'content',
    superAdminOnly: true
  },
  {
    key: 'news_count',
    label: '新闻总数',
    group: 'content',
    superAdminOnly: true
  },
  {
    key: 'news_view_count',
    label: '新闻累计浏览',
    group: 'content',
    superAdminOnly: true
  },
  {
    key: 'comment_processed_count',
    label: '评论处理量',
    group: 'moderation'
  },
  {
    key: 'report_processed_count',
    label: '举报处理量',
    group: 'moderation'
  },
  {
    key: 'feedback_processed_count',
    label: '反馈处理量',
    group: 'moderation'
  },
  { key: 'reward_stock', label: '奖品库存', group: 'rewards' },
  {
    key: 'pending_fulfillment_count',
    label: '待发放履约',
    group: 'rewards'
  },
  {
    key: 'points_issued',
    label: '积分发放总量',
    group: 'rewards',
    superAdminOnly: true
  },
  {
    key: 'redemption_count',
    label: '兑换笔数',
    group: 'rewards',
    superAdminOnly: true
  },
  {
    key: 'total_users',
    label: '总用户数',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'student_count',
    label: '学员数',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.student',
    label: '学员账户',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.teacher',
    label: '教师账户',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.enterprise',
    label: '企业账户',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.government',
    label: '政府账户',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.admin',
    label: '普通管理员账户',
    group: 'users',
    superAdminOnly: true
  },
  {
    key: 'role_distribution.super_admin',
    label: '超级管理员账户',
    group: 'users',
    superAdminOnly: true
  }
]

const groupMeta: Record<
  DashboardGroupId,
  { title: string; note: string }
> = {
  review: {
    title: '内容审核',
    note: '课程视频、招聘职位与非遗教学视频的待审核数量'
  },
  content: {
    title: '内容与数据',
    note: '已上架课程、在架职位、政策与新闻的累计数据'
  },
  moderation: {
    title: '评论与反馈',
    note: '评论、举报与意见反馈三类处理量的合计口径'
  },
  rewards: {
    title: '奖品与积分',
    note: '奖品库存、待发放履约、积分发放与兑换笔数'
  },
  users: {
    title: '账户分布',
    note: '按角色分类的平台账户总量与学员账户数量'
  }
}

const groupOrder: readonly DashboardGroupId[] = [
  'review',
  'content',
  'moderation',
  'rewards',
  'users'
]

const store = useAdminConsoleStore()

function metricTestId(key: string): string {
  return `dashboard-unavailable-${key
    .replace(/[._]+/g, '-')
    .replace(/[^a-zA-Z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()}`
}

function metricValue(
  dashboard: AdminDashboardSnapshot,
  key: string
): AdminDashboardMetric | undefined {
  let current: unknown = dashboard
  for (const segment of key.split('.')) {
    if (typeof current !== 'object' || current === null) return undefined
    current = (current as Record<string, unknown>)[segment]
  }
  if (typeof current === 'number' || typeof current === 'object') {
    return current as AdminDashboardMetric
  }
  return undefined
}

function isUnavailable(value: AdminDashboardMetric | undefined): boolean {
  return (
    typeof value === 'object' &&
    value !== null &&
    value.available === false
  )
}

const groups = computed<GroupView[]>(() => {
  const dashboard = store.dashboard
  if (dashboard === null) return []
  const isSuperAdmin = store.role === 'super_admin'
  const views: GroupView[] = []
  for (const id of groupOrder) {
    const definitions = metricDefinitions.filter(
      definition =>
        definition.group === id &&
        (isSuperAdmin || !definition.superAdminOnly)
    )
    if (definitions.length === 0) continue
    const metrics: Record<string, number> = {}
    const labels: Record<string, string> = {}
    const unavailable: Array<{ key: string; label: string }> = []
    for (const definition of definitions) {
      const value = metricValue(dashboard, definition.key)
      if (isUnavailable(value)) {
        unavailable.push({ key: definition.key, label: definition.label })
        continue
      }
      if (typeof value !== 'number') continue
      metrics[definition.key] = value
      labels[definition.key] = definition.label
    }
    views.push({
      id,
      title: groupMeta[id].title,
      note: groupMeta[id].note,
      metrics,
      labels,
      unavailable
    })
  }
  return views
})

const unavailableCount = computed(() =>
  groups.value.reduce((total, group) => total + group.unavailable.length, 0)
)

const hasMetrics = computed(() =>
  groups.value.some(
    group =>
      Object.keys(group.metrics).length > 0 || group.unavailable.length > 0
  )
)

onMounted(() => {
  void store.loadDashboard()
})
</script>

<template>
  <section class="admin-dashboard" data-test="admin-dashboard">
    <header class="dashboard-header">
      <div class="dashboard-header__identity">
        <Gauge :size="26" aria-hidden="true" />
        <div>
          <h1>数据看板</h1>
          <p>
            {{
              store.role === 'super_admin'
                ? '全平台账户、内容、监管与奖品指标汇总。'
                : '内容审核、监管与奖品运维指标汇总。'
            }}
          </p>
        </div>
      </div>
      <div class="dashboard-header__aside">
        <dl class="dashboard-header__summary">
          <div>
            <dt>指标分组</dt>
            <dd class="ark-data">{{ groups.length }}</dd>
          </div>
          <div>
            <dt>不可用来源</dt>
            <dd class="ark-data">{{ unavailableCount }}</dd>
          </div>
        </dl>
        <button
          type="button"
          class="dashboard-refresh"
          data-test="dashboard-refresh"
          aria-label="重新加载看板指标"
          title="重新加载看板指标"
          :disabled="store.loading"
          @click="store.loadDashboard()"
        >
          <RefreshCw :size="16" aria-hidden="true" />
        </button>
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
        :disabled="store.loading"
        @click="store.loadDashboard()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <div
      v-if="store.loading && store.dashboard === null"
      class="dashboard-state"
      data-test="dashboard-loading"
      role="status"
    >
      <RefreshCw class="spinning" :size="20" aria-hidden="true" />
      正在加载看板指标
    </div>

    <template v-else-if="store.dashboard !== null">
      <div
        v-if="!hasMetrics"
        class="dashboard-state dashboard-state--empty"
        data-test="dashboard-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无看板数据</span>
      </div>
      <template v-else>
        <section
          v-for="group in groups"
          :key="group.id"
          class="dashboard-group"
          :data-test="`dashboard-group-${group.id}`"
        >
          <header class="dashboard-group__heading">
            <h2>{{ group.title }}</h2>
            <span>{{ group.note }}</span>
          </header>
          <AdminMetricGroup
            v-if="Object.keys(group.metrics).length > 0"
            :metrics="group.metrics"
            :labels="group.labels"
          />
          <ul
            v-if="group.unavailable.length > 0"
            class="dashboard-unavailable"
            data-test="dashboard-unavailable"
          >
            <li
              v-for="item in group.unavailable"
              :key="item.key"
              :data-test="metricTestId(item.key)"
              :data-metric-key="item.key"
            >
              <AlertTriangle :size="15" aria-hidden="true" />
              <span>{{ item.label }}</span>
              <em>数据源不可用</em>
            </li>
          </ul>
        </section>
      </template>
    </template>

    <div
      v-else-if="!store.error"
      class="dashboard-state dashboard-state--empty"
      data-test="dashboard-empty"
    >
      <Inbox :size="24" aria-hidden="true" />
      <span>暂无看板数据</span>
    </div>
  </section>
</template>

<style scoped>
.admin-dashboard {
  min-width: 0;
  color: var(--ark-paper);
}

.dashboard-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dashboard-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.dashboard-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.dashboard-header__identity > div {
  min-width: 0;
}

.dashboard-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.dashboard-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-header__aside {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px;
  min-width: 0;
  align-items: stretch;
  gap: 1px;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.dashboard-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  background: var(--ark-line);
}

.dashboard-header__summary div {
  display: grid;
  min-width: 0;
  min-height: 76px;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.dashboard-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.dashboard-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.7rem;
  line-height: 1;
}

.dashboard-refresh {
  display: inline-grid;
  place-items: center;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.dashboard-refresh:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.dashboard-error,
.dashboard-state {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dashboard-error {
  color: var(--ark-paper);
}

.dashboard-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.dashboard-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-error button {
  display: inline-flex;
  min-height: 38px;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.dashboard-error button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.dashboard-state {
  min-height: 190px;
  align-items: center;
  justify-content: center;
  color: var(--ark-muted);
  text-align: center;
}

.dashboard-state--empty {
  flex-direction: column;
}

.dashboard-group {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dashboard-group__heading {
  display: flex;
  min-width: 0;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.dashboard-group__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.dashboard-group__heading span {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.75rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-unavailable {
  display: grid;
  gap: 1px;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  background: var(--ark-line);
}

.dashboard-unavailable li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-width: 0;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--ark-surface-1);
}

.dashboard-unavailable li > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.dashboard-unavailable li span {
  min-width: 0;
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dashboard-unavailable li em {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-style: normal;
  white-space: nowrap;
}

.admin-dashboard :is(button):focus-visible {
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

@media (max-width: 900px) {
  .dashboard-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard-header__aside {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .dashboard-header__identity {
    padding: 24px 20px;
  }
}

@media (max-width: 520px) {
  .dashboard-header__identity {
    padding: 21px 16px;
  }

  .dashboard-header__identity h1 {
    font-size: 2rem;
  }

  .dashboard-header__summary div {
    padding: 14px 16px;
  }

  .dashboard-error {
    flex-wrap: wrap;
  }

  .dashboard-error button {
    margin-left: 0;
  }

  .dashboard-unavailable li {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .dashboard-unavailable li em {
    grid-column: 2;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
