<script setup lang="ts">
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Flag,
  Inbox,
  MessageSquare,
  MessagesSquare,
  RefreshCw,
  ShieldAlert,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'

import type {
  AdminCommentReport,
  AdminCommentReportStatus,
  AdminFeedbackStatus,
  AdminModerationComment,
  AdminModerationCommentQuery,
  AdminModerationContentTypeFilter,
  AdminModerationFeedbackQuery,
  AdminModerationPerson,
  AdminModerationReportQuery,
  AdminModerationVisibilityFilter,
  AdminResolvedCommentReport,
  AdminUpdatedFeedbackRecord
} from '@/stores/adminConsole'
import { useAdminConsoleStore } from '@/stores/adminConsole'
import { widenModerationDay } from '@/stores/adminConsole'

type ModerationTab = 'comments' | 'reports' | 'feedback'

interface ModerationTabDefinition {
  id: ModerationTab
  label: string
  title: string
  icon: typeof MessagesSquare
}

const RESULT_MAX_LENGTH = 500

const contentTypeOptions: ReadonlyArray<{
  value: AdminModerationContentTypeFilter
  label: string
}> = [
  { value: 'all', label: '全部类型' },
  { value: 'course_video', label: '课程视频' },
  { value: 'handcraft_teaching_video', label: '非遗教学视频' }
]

const visibilityOptions: ReadonlyArray<{
  value: AdminModerationVisibilityFilter
  label: string
}> = [
  { value: 'all', label: '全部状态' },
  { value: 'visible', label: '可见' },
  { value: 'hidden', label: '已隐藏' }
]

const reportStatusOptions: ReadonlyArray<{
  value: AdminCommentReportStatus | 'all'
  label: string
}> = [
  { value: 'all', label: '全部举报' },
  { value: 'pending', label: '待处理' },
  { value: 'confirmed', label: '已确认' },
  { value: 'rejected', label: '已驳回' }
]

const feedbackStatusOptions: ReadonlyArray<{
  value: AdminFeedbackStatus | 'all'
  label: string
}> = [
  { value: 'all', label: '全部反馈' },
  { value: 'pending', label: '待处理' },
  { value: 'processed', label: '已处理' },
  { value: 'closed', label: '已关闭' }
]

const feedbackStatusLabels: Record<AdminFeedbackStatus, string> = {
  pending: '待处理',
  processed: '已处理',
  closed: '已关闭'
}

const reportStatusLabels: Record<AdminCommentReportStatus, string> = {
  pending: '待处理',
  confirmed: '已确认',
  rejected: '已驳回'
}

const tabs: ReadonlyArray<ModerationTabDefinition> = [
  {
    id: 'comments',
    label: '评论巡查',
    title: '评论列表',
    icon: MessageSquare
  },
  {
    id: 'reports',
    label: '举报处理',
    title: '举报队列',
    icon: Flag
  },
  {
    id: 'feedback',
    label: '意见反馈',
    title: '反馈队列',
    icon: MessagesSquare
  }
]

const emptyCommentFilters: AdminModerationCommentQuery = {
  content_type: 'all',
  content_id: '',
  author_id: '',
  keyword: '',
  is_visible: 'all',
  created_from: '',
  created_to: ''
}

const emptyReportFilters: AdminModerationReportQuery = {
  status: 'all',
  comment_id: '',
  reporter_id: '',
  created_from: '',
  created_to: ''
}

const emptyFeedbackFilters: AdminModerationFeedbackQuery = {
  status: 'all',
  submitter_id: '',
  created_from: '',
  created_to: ''
}

const store = useAdminConsoleStore()
const activeTab = ref<ModerationTab>('comments')
const commentFilters = ref<AdminModerationCommentQuery>({
  ...emptyCommentFilters
})
const reportFilters = ref<AdminModerationReportQuery>({ ...emptyReportFilters })
const feedbackFilters = ref<AdminModerationFeedbackQuery>({
  ...emptyFeedbackFilters
})
const pageSize = ref(20)
const commentsOffset = ref(0)
const reportsOffset = ref(0)
const feedbackOffset = ref(0)
// 总数恰为页大小整数倍时，最后一整页的“下一页”会越过末行进入空页。命中空页即锁止
// 前进并回退一页，使该空页永不对用户可见。
const commentsHitEnd = ref(false)
const reportsHitEnd = ref(false)
const feedbackHitEnd = ref(false)
const actionMessage = ref('')
const deleteCandidate = ref<AdminModerationComment | null>(null)
const reportCandidate = ref<{
  report: AdminCommentReport
  confirmed: boolean
} | null>(null)
const reportResult = ref('')
const feedbackDrafts = ref<Record<string, { status: AdminFeedbackStatus; result: string }>>(
  {}
)

let filterTimer: ReturnType<typeof setTimeout> | undefined

const activeTabDefinition = computed(
  () => tabs.find(tab => tab.id === activeTab.value) ?? tabs[0]
)

const pendingReportCount = computed(
  () => store.moderationReports.filter(item => item.status === 'pending').length
)

const pendingFeedbackCount = computed(
  () => store.moderationFeedback.filter(item => item.status === 'pending').length
)

const activeLoading = computed(() => {
  if (activeTab.value === 'comments') return store.moderationCommentsLoading
  if (activeTab.value === 'reports') return store.moderationReportsLoading
  return store.moderationFeedbackLoading
})

const activeError = computed(() => {
  if (activeTab.value === 'comments') return store.moderationCommentsError
  if (activeTab.value === 'reports') return store.moderationReportsError
  return store.moderationFeedbackError
})

const activeCount = computed(() => {
  if (activeTab.value === 'comments') return store.moderationCommentCount
  if (activeTab.value === 'reports') return store.moderationReportCount
  return store.moderationFeedbackCount
})

const activeOffset = computed(() => {
  if (activeTab.value === 'comments') return commentsOffset.value
  if (activeTab.value === 'reports') return reportsOffset.value
  return feedbackOffset.value
})

const activePage = computed(() => Math.floor(activeOffset.value / pageSize.value) + 1)

const canGoPrevious = computed(() => activeOffset.value > 0)

const activeHitEnd = computed(() => {
  if (activeTab.value === 'comments') return commentsHitEnd.value
  if (activeTab.value === 'reports') return reportsHitEnd.value
  return feedbackHitEnd.value
})

// A short page is the end of the queue: `count` is the number of rows this
// page carries, so a full page is the only signal that more rows may follow.
// 当总数恰为页大小整数倍时末页是整页，越过末行的一页返回 0 行，届时 `activeHitEnd`
// 会锁止前进，数据上的空页由此不可达。
const canGoNext = computed(
  () => activeCount.value >= pageSize.value && !activeHitEnd.value
)

const trimmedReportResult = computed(() => reportResult.value.trim())
const canSubmitReport = computed(
  () =>
    trimmedReportResult.value.length > 0 &&
    trimmedReportResult.value.length <= RESULT_MAX_LENGTH
)

function personLabel(person: AdminModerationPerson | undefined, id: number): string {
  const name = person?.name?.trim()
  if (name) return name
  const username = person?.username?.trim()
  if (username) return username
  return `用户 #${id}`
}

function contentTypeLabel(contentType: string): string {
  return (
    contentTypeOptions.find(option => option.value === contentType)?.label ??
    contentType
  )
}

function reportStatusLabel(status: string): string {
  return reportStatusLabels[status as AdminCommentReportStatus] ?? status
}

function feedbackStatusLabel(status: string): string {
  return feedbackStatusLabels[status as AdminFeedbackStatus] ?? status
}

function formatTime(value: string | null): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

// 加宽查询仅做一次：`widenModerationDay` 幂等，故同一批过滤条件无论被 settlePage 读取
// 多少次都不会二次拼时区。若一页返回 0 行且已离开首页，说明上一整页之后没有更多数据
// （总数恰为页大小整数倍），于是锁止前进并回退一页。
async function settlePage<
  Q extends { created_from: string; created_to: string }
>(
  filters: Q,
  offset: Ref<number>,
  endReached: Ref<boolean>,
  load: (query: Q, offset: number) => Promise<boolean>,
  count: () => number
): Promise<void> {
  const query = { ...filters, ...widenModerationDay(filters) } as Q
  const ok = await load(query, offset.value)
  if (!ok) return
  if (offset.value > 0 && count() === 0) {
    endReached.value = true
    offset.value = Math.max(0, offset.value - pageSize.value)
    await load(query, offset.value)
    return
  }
  if (offset.value === 0 || count() < pageSize.value) {
    endReached.value = false
  }
}

function reloadComments(): void {
  void settlePage<AdminModerationCommentQuery>(
    commentFilters.value,
    commentsOffset,
    commentsHitEnd,
    (query, offset) =>
      store.loadModerationComments(query, offset, pageSize.value),
    () => store.moderationCommentCount
  )
}

function reloadReports(): void {
  void settlePage<AdminModerationReportQuery>(
    reportFilters.value,
    reportsOffset,
    reportsHitEnd,
    (query, offset) =>
      store.loadModerationReports(query, offset, pageSize.value),
    () => store.moderationReportCount
  )
}

function reloadFeedback(): void {
  void settlePage<AdminModerationFeedbackQuery>(
    feedbackFilters.value,
    feedbackOffset,
    feedbackHitEnd,
    (query, offset) =>
      store.loadModerationFeedback(query, offset, pageSize.value),
    () => store.moderationFeedbackCount
  )
}

function reloadActive(): void {
  if (activeTab.value === 'comments') {
    reloadComments()
    return
  }
  if (activeTab.value === 'reports') {
    reloadReports()
    return
  }
  reloadFeedback()
}

function scheduleActiveReload(): void {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
  filterTimer = setTimeout(reloadActive, 240)
}

// Every filter field of the open tab feeds the same debounced reload, and the
// apply button clears the timer so a confirmed filter never waits on it.
watch(
  () => ({ ...commentFilters.value }),
  () => {
    if (activeTab.value !== 'comments') return
    commentsOffset.value = 0
    scheduleActiveReload()
  }
)

watch(
  () => ({ ...reportFilters.value }),
  () => {
    if (activeTab.value !== 'reports') return
    reportsOffset.value = 0
    scheduleActiveReload()
  }
)

watch(
  () => ({ ...feedbackFilters.value }),
  () => {
    if (activeTab.value !== 'feedback') return
    feedbackOffset.value = 0
    scheduleActiveReload()
  }
)

watch(pageSize, () => {
  commentsOffset.value = 0
  reportsOffset.value = 0
  feedbackOffset.value = 0
  // A page size is a discrete choice, so it applies without waiting on the
  // debounce that text filters use.
  reloadActive()
})

function selectTab(tab: ModerationTab): void {
  if (tab === activeTab.value) return
  activeTab.value = tab
  actionMessage.value = ''
  closeDialogs()
  reloadActive()
}

function applyFilters(): void {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
  commentsOffset.value = 0
  reportsOffset.value = 0
  feedbackOffset.value = 0
  reloadActive()
}

function resetFilters(): void {
  commentFilters.value = { ...emptyCommentFilters }
  reportFilters.value = { ...emptyReportFilters }
  feedbackFilters.value = { ...emptyFeedbackFilters }
  pageSize.value = 20
  applyFilters()
}

function changePage(direction: 'previous' | 'next'): void {
  if (direction === 'previous' && !canGoPrevious.value) return
  if (direction === 'next' && !canGoNext.value) return
  const step = direction === 'previous' ? -pageSize.value : pageSize.value
  if (activeTab.value === 'comments') {
    commentsOffset.value = Math.max(0, commentsOffset.value + step)
  } else if (activeTab.value === 'reports') {
    reportsOffset.value = Math.max(0, reportsOffset.value + step)
  } else {
    feedbackOffset.value = Math.max(0, feedbackOffset.value + step)
  }
  reloadActive()
}

function retryActive(): void {
  reloadActive()
}

function commentLabel(comment: AdminModerationComment): string {
  return comment.body.trim() || comment.comment_id
}

// A reply whose parent left the current page keeps its own row: the patrol
// queue lists comments, not threads, so the parent is reported as hidden
// instead of being rendered as a dangling reference.
function parentLabel(comment: AdminModerationComment): string | null {
  if (comment.parent_comment_id === null) return null
  const parent = store.moderationComments.find(
    item => item.comment_id === comment.parent_comment_id
  )
  if (!parent) return '原评论已隐藏'
  const preview = parent.body.trim()
  return preview ? `回复：${preview}` : '回复：该评论无正文'
}

function openDelete(comment: AdminModerationComment): void {
  if (comment.is_visible === false) return
  actionMessage.value = ''
  store.clearModerationCommentsError()
  deleteCandidate.value = comment
}

function closeDialogs(): void {
  deleteCandidate.value = null
  reportCandidate.value = null
  reportResult.value = ''
}

async function confirmDelete(): Promise<void> {
  const comment = deleteCandidate.value
  if (comment === null) return
  const result = await store.deleteModerationComment(comment.comment_id)
  if (result === null) return
  actionMessage.value = result.changed
    ? `已隐藏评论 ${comment.comment_id}，不会通知作者与相关用户`
    : `评论 ${comment.comment_id} 此前已隐藏，未产生新的处理`
  closeDialogs()
}

function openReport(
  report: AdminCommentReport,
  confirmed: boolean
): void {
  if (report.status !== 'pending') return
  actionMessage.value = ''
  store.clearModerationReportsError()
  reportResult.value = ''
  reportCandidate.value = { report, confirmed }
}

async function confirmReport(): Promise<void> {
  const candidate = reportCandidate.value
  if (candidate === null || !canSubmitReport.value) return
  const resolved = await store.resolveModerationReport(
    candidate.report.report_id,
    candidate.confirmed,
    trimmedReportResult.value
  )
  if (resolved === null) return
  actionMessage.value = describeResolvedReport(resolved, candidate.confirmed)
  closeDialogs()
}

function describeResolvedReport(
  resolved: AdminResolvedCommentReport,
  confirmed: boolean
): string {
  const outcome = confirmed ? '已确认举报' : '已驳回举报'
  if (!resolved.changed) {
    return `该举报此前已处理，界面显示已存储的决定（${outcome}）`
  }
  return confirmed
    ? `${outcome}，已隐藏评论，不会通知举报人与作者`
    : `${outcome}，不会通知举报人与作者`
}

function feedbackDraft(feedbackId: string, status: AdminFeedbackStatus) {
  const existing = feedbackDrafts.value[feedbackId]
  if (existing) return existing
  return { status, result: '' }
}

function setFeedbackStatus(feedbackId: string, status: AdminFeedbackStatus): void {
  const draft = feedbackDrafts.value[feedbackId] ?? { status, result: '' }
  feedbackDrafts.value = {
    ...feedbackDrafts.value,
    [feedbackId]: { status, result: draft.result }
  }
}

// The row's stored status seeds a draft that has only seen the note field, so
// the menu and the submitted status can never disagree.
function setFeedbackResult(
  feedbackId: string,
  status: AdminFeedbackStatus,
  result: string
): void {
  const draft = feedbackDrafts.value[feedbackId] ?? { status, result: '' }
  feedbackDrafts.value = {
    ...feedbackDrafts.value,
    [feedbackId]: { status: draft.status, result }
  }
}

async function submitFeedback(
  feedbackId: string,
  fallbackStatus: AdminFeedbackStatus
): Promise<void> {
  const draft = feedbackDraft(feedbackId, fallbackStatus)
  const result = draft.result.trim()
  if (!result) return
  const updated = await store.updateModerationFeedback(
    feedbackId,
    draft.status,
    result
  )
  if (updated === null) return
  actionMessage.value = updated.changed
    ? `反馈 ${feedbackId} 已标记为「${feedbackStatusLabel(updated.status)}」，不会通知提交人`
    : `反馈 ${feedbackId} 此前已是「${feedbackStatusLabel(updated.status)}」，未产生新的处理`
  feedbackDrafts.value = {
    ...feedbackDrafts.value,
    [feedbackId]: { status: updated.status, result: '' }
  }
}

onMounted(reloadComments)

onBeforeUnmount(() => {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
})
</script>

<template>
  <section class="admin-moderation" data-test="admin-moderation">
    <header class="mod-header">
      <div class="mod-header__identity">
        <MessagesSquare :size="26" aria-hidden="true" />
        <div>
          <h1>评论监管</h1>
          <p>
            评论巡查、举报处理与意见反馈都在此处闭环，所有处理都不会通知作者、举报人或提交人。
          </p>
        </div>
      </div>
      <dl class="mod-header__summary">
        <div>
          <dt>本页评论</dt>
          <dd class="ark-data">{{ store.moderationCommentCount }}</dd>
        </div>
        <div>
          <dt>待处理举报</dt>
          <dd class="ark-data" data-test="moderation-pending-reports">
            {{ pendingReportCount }}
          </dd>
        </div>
        <div>
          <dt>待处理反馈</dt>
          <dd class="ark-data" data-test="moderation-pending-feedback">
            {{ pendingFeedbackCount }}
          </dd>
        </div>
      </dl>
    </header>

    <div
      class="mod-tabs"
      role="tablist"
      aria-label="评论监管队列"
      data-test="moderation-tabs"
    >
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :data-test="`moderation-tab-${tab.id}`"
        :class="{ 'is-active': activeTab === tab.id }"
        :aria-selected="activeTab === tab.id"
        @click="selectTab(tab.id)"
      >
        <component :is="tab.icon" :size="16" aria-hidden="true" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <p
      v-if="actionMessage"
      class="mod-message"
      data-test="moderation-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ actionMessage }}
    </p>

    <div
      v-if="activeError"
      class="mod-error"
      data-test="moderation-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ activeError }}</span>
      <button
        type="button"
        data-test="moderation-retry"
        :disabled="activeLoading"
        @click="retryActive"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="mod-filters" aria-label="监管队列筛选">
      <div v-if="activeTab === 'comments'" class="mod-filter-grid">
        <label class="mod-field">
          <span>内容类型</span>
          <select v-model="commentFilters.content_type" data-test="moderation-content-type">
            <option v-for="option in contentTypeOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="mod-field">
          <span>内容 ID</span>
          <input
            v-model="commentFilters.content_id"
            type="search"
            data-test="moderation-content-id"
            placeholder="课程或视频 ID"
          />
        </label>
        <label class="mod-field">
          <span>作者 ID</span>
          <input
            v-model="commentFilters.author_id"
            type="search"
            inputmode="numeric"
            data-test="moderation-author-id"
            placeholder="用户 ID"
          />
        </label>
        <label class="mod-field">
          <span>关键词</span>
          <input
            v-model="commentFilters.keyword"
            type="search"
            data-test="moderation-keyword"
            placeholder="评论内容或作者"
          />
        </label>
        <label class="mod-field">
          <span>可见状态</span>
          <select v-model="commentFilters.is_visible" data-test="moderation-visibility">
            <option v-for="option in visibilityOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="mod-field">
          <span>开始日期</span>
          <input v-model="commentFilters.created_from" type="date" data-test="moderation-from" />
        </label>
        <label class="mod-field">
          <span>结束日期</span>
          <input v-model="commentFilters.created_to" type="date" data-test="moderation-to" />
        </label>
      </div>

      <div v-else-if="activeTab === 'reports'" class="mod-filter-grid">
        <label class="mod-field">
          <span>举报状态</span>
          <select v-model="reportFilters.status" data-test="moderation-report-status">
            <option v-for="option in reportStatusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="mod-field">
          <span>评论 ID</span>
          <input
            v-model="reportFilters.comment_id"
            type="search"
            data-test="moderation-comment-id"
            placeholder="被举报评论 ID"
          />
        </label>
        <label class="mod-field">
          <span>举报人 ID</span>
          <input
            v-model="reportFilters.reporter_id"
            type="search"
            inputmode="numeric"
            data-test="moderation-reporter-id"
            placeholder="用户 ID"
          />
        </label>
        <label class="mod-field">
          <span>开始日期</span>
          <input v-model="reportFilters.created_from" type="date" data-test="moderation-reports-from" />
        </label>
        <label class="mod-field">
          <span>结束日期</span>
          <input v-model="reportFilters.created_to" type="date" data-test="moderation-reports-to" />
        </label>
      </div>

      <div v-else class="mod-filter-grid">
        <label class="mod-field">
          <span>反馈状态</span>
          <select v-model="feedbackFilters.status" data-test="moderation-feedback-status">
            <option v-for="option in feedbackStatusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="mod-field">
          <span>提交人 ID</span>
          <input
            v-model="feedbackFilters.submitter_id"
            type="search"
            inputmode="numeric"
            data-test="moderation-submitter-id"
            placeholder="用户 ID"
          />
        </label>
        <label class="mod-field">
          <span>开始日期</span>
          <input v-model="feedbackFilters.created_from" type="date" data-test="moderation-feedback-from" />
        </label>
        <label class="mod-field">
          <span>结束日期</span>
          <input v-model="feedbackFilters.created_to" type="date" data-test="moderation-feedback-to" />
        </label>
      </div>

      <div class="mod-filters__actions">
        <label class="mod-field mod-field--page">
          <span>每页条数</span>
          <select v-model="pageSize" data-test="moderation-page-size">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </label>
        <button
          type="button"
          data-test="moderation-apply"
          :disabled="activeLoading"
          @click="applyFilters"
        >
          应用筛选
        </button>
        <button
          type="button"
          data-test="moderation-reset"
          :disabled="activeLoading"
          @click="resetFilters"
        >
          重置
        </button>
      </div>
    </section>

    <section class="mod-registry" aria-labelledby="mod-registry-title">
      <header class="mod-registry__heading">
        <h2 id="mod-registry-title">{{ activeTabDefinition.title }}</h2>
        <div class="mod-registry__meta">
          <span class="ark-data" data-test="moderation-count">本页 {{ activeCount }} 条</span>
          <span class="ark-data" data-test="moderation-page">第 {{ activePage }} 页</span>
        </div>
      </header>

      <div
        v-if="activeLoading && activeCount === 0"
        class="mod-state"
        data-test="moderation-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载{{ activeTabDefinition.title }}
      </div>

      <div
        v-else-if="activeCount === 0"
        class="mod-state mod-state--empty"
        data-test="moderation-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>当前筛选条件下没有{{ activeTabDefinition.title }}</span>
      </div>

      <div v-else class="mod-table-wrap">
        <table v-if="activeTab === 'comments'" class="mod-table">
          <thead>
            <tr>
              <th scope="col">评论</th>
              <th scope="col">内容</th>
              <th scope="col">作者</th>
              <th scope="col">回复关系</th>
              <th scope="col">状态</th>
              <th scope="col">创建时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="comment in store.moderationComments"
              :key="comment.comment_id"
              data-test="comment-row"
              :data-comment-id="comment.comment_id"
            >
              <td data-label="评论">
                <div class="mod-cell">
                  <strong>{{ commentLabel(comment) }}</strong>
                  <span class="mod-sub ark-data">{{ comment.comment_id }}</span>
                </div>
              </td>
              <td data-label="内容">
                <div class="mod-cell">
                  <span>{{ contentTypeLabel(comment.content_type) }}</span>
                  <span class="mod-sub ark-data">{{ comment.content_id }}</span>
                </div>
              </td>
              <td data-label="作者">{{ personLabel(comment.author, comment.author_id) }}</td>
              <td data-label="回复关系">
                <span v-if="parentLabel(comment)" class="mod-parent" data-test="comment-parent">
                  {{ parentLabel(comment) }}
                </span>
                <span v-else class="mod-processed">主评论</span>
              </td>
              <td data-label="状态">
                <span
                  class="mod-status"
                  :class="comment.is_visible ? 'is-visible' : 'is-hidden'"
                  data-test="comment-visibility"
                >
                  {{ comment.is_visible ? '可见' : '已隐藏' }}
                </span>
              </td>
              <td data-label="创建时间">
                <time class="ark-data" :datetime="comment.created_at || undefined">
                  {{ formatTime(comment.created_at) }}
                </time>
              </td>
              <td data-label="操作">
                <button
                  v-if="comment.is_visible"
                  type="button"
                  :data-test="`comment-delete-${comment.comment_id}`"
                  :aria-label="`隐藏评论：${comment.comment_id}`"
                  :title="`隐藏评论：${comment.comment_id}`"
                  :disabled="store.moderationCommentActionLoading"
                  @click="openDelete(comment)"
                >
                  <Trash2 :size="16" aria-hidden="true" />
                  隐藏
                </button>
                <span v-else class="mod-processed" data-test="comment-hidden">已隐藏</span>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="activeTab === 'reports'" class="mod-table">
          <thead>
            <tr>
              <th scope="col">举报</th>
              <th scope="col">被举报评论</th>
              <th scope="col">举报人</th>
              <th scope="col">状态</th>
              <th scope="col">处理结果</th>
              <th scope="col">举报时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="report in store.moderationReports"
              :key="report.report_id"
              data-test="report-row"
              :data-report-id="report.report_id"
            >
              <td data-label="举报">
                <div class="mod-cell">
                  <strong>{{ report.reason }}</strong>
                  <span class="mod-sub ark-data">{{ report.report_id }}</span>
                </div>
              </td>
              <td data-label="被举报评论">
                <div class="mod-cell">
                  <span class="ark-data">{{ report.comment_id }}</span>
                  <span
                    v-if="report.comment_is_visible === false"
                    class="mod-sub"
                    data-test="report-comment-hidden"
                  >
                    评论已隐藏
                  </span>
                  <span v-else-if="report.comment_is_visible === null" class="mod-sub">
                    评论已删除
                  </span>
                </div>
              </td>
              <td data-label="举报人">
                {{ personLabel(report.reporter, report.reporter_id) }}
              </td>
              <td data-label="状态">
                <span
                  class="mod-status"
                  :class="report.status === 'pending' ? 'is-pending' : 'is-processed'"
                  data-test="report-status"
                >
                  {{ reportStatusLabel(report.status) }}
                </span>
              </td>
              <td data-label="处理结果">
                <div v-if="report.status === 'pending'" class="mod-processed">尚未处理</div>
                <div v-else class="mod-cell">
                  <strong data-test="report-decision">{{ report.result }}</strong>
                  <span class="mod-sub">
                    {{ report.resolver_id === null ? '处理人未知' : personLabel(report.resolver, report.resolver_id) }}
                    <time class="ark-data" :datetime="report.resolved_at || undefined">
                      {{ formatTime(report.resolved_at) }}
                    </time>
                  </span>
                </div>
              </td>
              <td data-label="举报时间">
                <time class="ark-data" :datetime="report.created_at || undefined">
                  {{ formatTime(report.created_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div v-if="report.status === 'pending'" class="mod-actions">
                  <button
                    type="button"
                    :data-test="`report-confirm-${report.report_id}`"
                    :aria-label="`确认举报：${report.report_id}`"
                    :title="`确认举报：${report.report_id}`"
                    :disabled="store.moderationReportActionLoading"
                    @click="openReport(report, true)"
                  >
                    <Check :size="16" aria-hidden="true" />
                    确认
                  </button>
                  <button
                    type="button"
                    :data-test="`report-reject-${report.report_id}`"
                    :aria-label="`驳回举报：${report.report_id}`"
                    :title="`驳回举报：${report.report_id}`"
                    :disabled="store.moderationReportActionLoading"
                    @click="openReport(report, false)"
                  >
                    <X :size="16" aria-hidden="true" />
                    驳回
                  </button>
                </div>
                <span v-else class="mod-processed" data-test="report-processed">
                  已处理，不可改判
                </span>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else class="mod-table">
          <thead>
            <tr>
              <th scope="col">反馈</th>
              <th scope="col">提交人</th>
              <th scope="col">状态</th>
              <th scope="col">处理结果</th>
              <th scope="col">提交时间</th>
              <th scope="col">处理操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="feedback in store.moderationFeedback"
              :key="feedback.feedback_id"
              data-test="feedback-row"
              :data-feedback-id="feedback.feedback_id"
            >
              <td data-label="反馈">
                <div class="mod-cell">
                  <strong>{{ feedback.body }}</strong>
                  <span class="mod-sub ark-data">{{ feedback.feedback_id }}</span>
                </div>
              </td>
              <td data-label="提交人">
                {{ personLabel(feedback.submitter, feedback.submitter_id) }}
              </td>
              <td data-label="状态">
                <span
                  class="mod-status"
                  :class="feedback.status === 'pending' ? 'is-pending' : 'is-processed'"
                  data-test="feedback-status"
                >
                  {{ feedbackStatusLabel(feedback.status) }}
                </span>
              </td>
              <td data-label="处理结果">
                <span v-if="feedback.result" data-test="feedback-result">{{ feedback.result }}</span>
                <span v-else class="mod-processed">尚未填写</span>
              </td>
              <td data-label="提交时间">
                <time class="ark-data" :datetime="feedback.created_at || undefined">
                  {{ formatTime(feedback.created_at) }}
                </time>
              </td>
              <td data-label="处理操作">
                <div class="mod-feedback-actions">
                  <label class="mod-field">
                    <span class="ark-sr-only">处理状态</span>
                    <select
                      :value="feedbackDraft(feedback.feedback_id, feedback.status).status"
                      :data-test="`feedback-status-${feedback.feedback_id}`"
                      :disabled="store.moderationFeedbackActionLoading"
                      @change="setFeedbackStatus(feedback.feedback_id, ($event.target as HTMLSelectElement).value as AdminFeedbackStatus)"
                    >
                      <option value="pending">待处理</option>
                      <option value="processed">已处理</option>
                      <option value="closed">已关闭</option>
                    </select>
                  </label>
                  <input
                    :value="feedbackDraft(feedback.feedback_id, feedback.status).result"
                    type="text"
                    maxlength="500"
                    placeholder="处理结果备注（必填）"
                    :data-test="`feedback-result-${feedback.feedback_id}`"
                    :disabled="store.moderationFeedbackActionLoading"
                    @input="setFeedbackResult(feedback.feedback_id, feedback.status, ($event.target as HTMLInputElement).value)"
                  />
                  <button
                    type="button"
                    :data-test="`feedback-submit-${feedback.feedback_id}`"
                    :disabled="
                      store.moderationFeedbackActionLoading ||
                      feedbackDraft(feedback.feedback_id, feedback.status).result.trim().length === 0
                    "
                    @click="submitFeedback(feedback.feedback_id, feedback.status)"
                  >
                    提交
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="mod-pagination" data-test="moderation-pagination">
        <button
          type="button"
          data-test="moderation-prev"
          :disabled="!canGoPrevious || activeLoading"
          @click="changePage('previous')"
        >
          <ChevronLeft :size="16" aria-hidden="true" />
          上一页
        </button>
        <span class="mod-pagination__hint">
          每页 {{ pageSize }} 条，翻页按当前筛选条件继续查询
        </span>
        <button
          type="button"
          data-test="moderation-next"
          :disabled="!canGoNext || activeLoading"
          @click="changePage('next')"
        >
          下一页
          <ChevronRight :size="16" aria-hidden="true" />
        </button>
      </footer>
    </section>

    <div
      v-if="deleteCandidate"
      class="mod-dialog-backdrop"
      data-test="comment-delete-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="mod-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comment-delete-title"
      >
        <header>
          <h2 id="comment-delete-title">隐藏评论</h2>
          <button
            type="button"
            aria-label="关闭隐藏评论对话框"
            title="关闭"
            :disabled="store.moderationCommentActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p data-test="comment-delete-notice">
          隐藏后学员端与教师端都不再返回这条评论。
          <strong>系统不会发送通知</strong>，作者与相关用户都不会被告知；
          该评论下的回复仍然可见，父子评论的可见性不级联。
        </p>
        <p class="mod-dialog__quote">{{ commentLabel(deleteCandidate) }}</p>
        <div class="mod-dialog__actions">
          <button
            type="button"
            data-test="confirm-comment-delete"
            :disabled="store.moderationCommentActionLoading"
            @click="confirmDelete"
          >
            <Trash2 :size="16" aria-hidden="true" />
            {{ store.moderationCommentActionLoading ? '正在处理' : '确认隐藏' }}
          </button>
          <button
            type="button"
            :disabled="store.moderationCommentActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>

    <div
      v-if="reportCandidate"
      class="mod-dialog-backdrop"
      :data-test="reportCandidate.confirmed ? 'report-confirm-dialog' : 'report-reject-dialog'"
      @click.self="closeDialogs"
    >
      <section
        class="mod-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-resolve-title"
      >
        <header>
          <h2 id="report-resolve-title">
            {{ reportCandidate.confirmed ? '确认举报' : '驳回举报' }}
          </h2>
          <button
            type="button"
            aria-label="关闭举报处理对话框"
            title="关闭"
            :disabled="store.moderationReportActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p data-test="report-resolve-notice">
          {{
            reportCandidate.confirmed
              ? '确认后将隐藏被举报的评论，并把这条举报标记为已确认。'
              : '驳回后保留被举报评论的可见性，并把这条举报标记为已驳回。'
          }}
          处理过程<strong>不会发送通知</strong>，举报人与作者都不会被告知。
        </p>
        <label class="mod-opinion">
          <span>处理备注（必填）</span>
          <textarea
            v-model="reportResult"
            data-test="report-result"
            maxlength="500"
            rows="5"
            placeholder="说明确认或驳回的依据"
          />
        </label>
        <div class="mod-opinion__meta">
          <span class="ark-data" data-test="report-result-count">
            {{ trimmedReportResult.length }} / 500
          </span>
          <span v-if="!trimmedReportResult.length">去除空白后不能为空</span>
        </div>
        <div class="mod-dialog__actions">
          <button
            type="button"
            :data-test="reportCandidate.confirmed ? 'confirm-report-action' : 'confirm-report-reject'"
            :disabled="!canSubmitReport || store.moderationReportActionLoading"
            @click="confirmReport"
          >
            <Check :size="16" aria-hidden="true" />
            {{
              store.moderationReportActionLoading
                ? '正在处理'
                : reportCandidate.confirmed
                  ? '确认举报'
                  : '确认驳回'
            }}
          </button>
          <button
            type="button"
            :disabled="store.moderationReportActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-moderation {
  min-width: 0;
  color: var(--ark-paper);
}

.mod-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, 0.58fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.mod-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.mod-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.mod-header__identity > div {
  min-width: 0;
}

.mod-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.mod-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.mod-header__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.mod-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 20px 16px;
  background: var(--ark-surface-1);
}

.mod-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.8rem;
  line-height: 1;
}

.mod-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.mod-tabs button {
  display: flex;
  min-width: 0;
  min-height: 56px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 12px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.mod-tabs button:hover,
.mod-tabs button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.mod-tabs button.is-active {
  box-shadow: inset 0 -2px 0 var(--ark-signal);
  color: var(--ark-signal);
}

.mod-tabs button span {
  min-width: 0;
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-message,
.mod-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.mod-message {
  color: var(--ark-state);
}

.mod-message svg,
.mod-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.mod-message,
.mod-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.mod-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-filters {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.mod-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.mod-field {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  background: var(--ark-surface-0);
}

.mod-field > span {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-field input,
.mod-field select {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-field input:hover,
.mod-field select:hover {
  border-color: var(--ark-signal);
}

.mod-filters__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid var(--ark-line);
}

.mod-filters__actions .mod-field {
  flex: 0 1 150px;
  padding: 0;
  background: transparent;
}

.mod-filters__actions button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-filters__actions button:first-of-type {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.mod-registry {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.mod-registry__heading {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.mod-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.mod-registry__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.mod-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.mod-state--empty {
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 10px;
}

.mod-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.mod-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.mod-table th,
.mod-table td {
  min-width: 0;
  padding: 14px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.mod-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
}

.mod-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.mod-table th:nth-child(1) {
  width: 24%;
}

.mod-table th:nth-child(2) {
  width: 16%;
}

.mod-table th:nth-child(3) {
  width: 12%;
}

.mod-table th:nth-child(4) {
  width: 14%;
}

.mod-table th:nth-child(5) {
  width: 12%;
}

.mod-table th:nth-child(6) {
  width: 12%;
}

.mod-table th:nth-child(7) {
  width: 10%;
}

.mod-table tbody tr:last-child td {
  border-bottom: 0;
}

.mod-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.mod-cell strong {
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.mod-sub,
.mod-parent,
.mod-processed {
  color: var(--ark-muted);
  font-size: 0.7rem;
  line-height: 1.5;
}

.mod-sub time {
  display: block;
}

.mod-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.mod-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.mod-status.is-visible,
.mod-status.is-pending {
  color: var(--ark-signal);
}

.mod-status.is-hidden,
.mod-status.is-processed {
  color: var(--ark-muted);
}

.mod-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mod-actions button,
.mod-feedback-actions button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-actions button {
  flex: 1 1 72px;
}

.mod-actions button:first-child,
.mod-feedback-actions button {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.mod-feedback-actions {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.mod-feedback-actions .mod-field {
  padding: 0;
  background: transparent;
}

.mod-feedback-actions input {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 18px;
  border-top: 1px solid var(--ark-line);
}

.mod-pagination button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-pagination__hint {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--ark-paper) 72%, transparent);
}

.mod-dialog {
  width: min(100%, 560px);
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.mod-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.mod-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.mod-dialog header button {
  display: inline-grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.mod-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.mod-dialog > p strong {
  color: var(--ark-paper);
}

.mod-dialog__quote {
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.mod-opinion {
  display: grid;
  gap: 7px;
  padding: 16px 18px 0;
}

.mod-opinion > span,
.mod-opinion__meta {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.mod-opinion textarea {
  width: 100%;
  min-width: 0;
  min-height: 132px;
  padding: 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  resize: vertical;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.mod-opinion textarea:hover {
  border-color: var(--ark-signal);
}

.mod-opinion__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 18px 0;
}

.mod-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.mod-dialog__actions button {
  display: inline-flex;
  min-width: 108px;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.mod-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.admin-moderation :is(button, input, select, textarea):focus-visible {
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
  .mod-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .mod-tabs {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .mod-table-wrap {
    overflow-x: visible;
  }

  .mod-table,
  .mod-table tbody {
    display: block;
  }

  .mod-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .mod-table tbody {
    display: grid;
    gap: 1px;
    background: var(--ark-line);
  }

  .mod-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .mod-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .mod-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }

  .mod-table td:last-child {
    border-bottom: 0;
  }

  .mod-cell {
    justify-items: end;
    text-align: right;
  }

  .mod-actions {
    justify-content: flex-end;
  }

  .mod-feedback-actions {
    justify-items: stretch;
  }
}

@media (max-width: 520px) {
  .mod-header__identity {
    padding: 21px 16px;
  }

  .mod-header__identity h1 {
    font-size: 2rem;
  }

  .mod-header__summary {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-tabs {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-filters__actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: end;
  }

  .mod-filters__actions .mod-field {
    grid-column: 1 / -1;
  }

  .mod-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-cell {
    justify-items: start;
    text-align: left;
  }

  .mod-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .mod-feedback-actions {
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-feedback-actions button {
    width: 100%;
  }

  .mod-pagination {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .mod-pagination__hint {
    grid-column: 1 / -1;
    grid-row: 1;
  }

  .mod-dialog-backdrop {
    padding: 10px;
  }

  .mod-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .mod-dialog__actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
