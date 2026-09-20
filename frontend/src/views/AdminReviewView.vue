<script setup lang="ts">
import {
  Check,
  ClipboardCheck,
  Inbox,
  RefreshCw,
  ShieldAlert,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type {
  AdminReviewContentType,
  AdminReviewItem,
  AdminReviewStatus
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

type ReviewFilter = 'all' | AdminReviewContentType

const contentTypeOptions: ReadonlyArray<{
  value: AdminReviewContentType
  label: string
}> = [
  { value: 'course_video', label: '课程视频' },
  { value: 'job_position', label: '招聘职位' },
  { value: 'handcraft_teaching_video', label: '非遗教学视频' }
]

const statusLabels: Record<AdminReviewStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  offline: '已下架'
}

const store = useAdminConsoleStore()
const activeFilter = ref<ReviewFilter>('all')
const approveCandidate = ref<AdminReviewItem | null>(null)
const rejectCandidate = ref<AdminReviewItem | null>(null)
const opinion = ref('')
const actionMessage = ref('')

const filteredItems = computed(() =>
  activeFilter.value === 'all'
    ? store.reviewItems
    : store.reviewItems.filter(
        item => item.content_type === activeFilter.value
      )
)

const totalPending = computed(() =>
  contentTypeOptions.reduce(
    (total, option) => total + store.reviewCounts[option.value],
    0
  )
)

const trimmedOpinion = computed(() => opinion.value.trim())
const canSubmitReject = computed(
  () =>
    trimmedOpinion.value.length > 0 &&
    trimmedOpinion.value.length <= 500
)

function contentLabel(contentType: AdminReviewContentType): string {
  return (
    contentTypeOptions.find(option => option.value === contentType)?.label ??
    contentType
  )
}

function statusLabel(status: AdminReviewStatus): string {
  return statusLabels[status] ?? status
}

function submitterLabel(item: AdminReviewItem): string {
  return (
    item.submitter_name ||
    item.owner_name ||
    (item.submitter_id === null ? '未知提交者' : `用户 #${item.submitter_id}`)
  )
}

function formatUpdatedAt(value: string | null): string {
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

function openApprove(item: AdminReviewItem) {
  if (item.review_status !== 'pending' || item.version === null) return
  actionMessage.value = ''
  approveCandidate.value = item
}

function openReject(item: AdminReviewItem) {
  if (item.review_status !== 'pending' || item.version === null) return
  actionMessage.value = ''
  opinion.value = ''
  rejectCandidate.value = item
}

function closeDialogs() {
  approveCandidate.value = null
  rejectCandidate.value = null
  opinion.value = ''
}

async function confirmApprove() {
  const item = approveCandidate.value
  if (item === null || item.version === null) return
  const success = await store.approveReview(
    item.content_type,
    item.content_id,
    item.version
  )
  if (success) {
    actionMessage.value = `已通过「${item.title || item.content_id}」`
    closeDialogs()
  }
}

async function confirmReject() {
  const item = rejectCandidate.value
  if (
    item === null ||
    item.version === null ||
    !canSubmitReject.value
  ) {
    return
  }
  const success = await store.rejectReview(
    item.content_type,
    item.content_id,
    item.version,
    trimmedOpinion.value
  )
  if (success) {
    actionMessage.value = `已驳回「${item.title || item.content_id}」`
    closeDialogs()
  }
}

onMounted(() => {
  void store.loadReviewQueue()
})
</script>

<template>
  <section class="admin-review-page" data-test="admin-review">
    <header class="review-header">
      <div class="review-header__identity">
        <ClipboardCheck :size="26" aria-hidden="true" />
        <div>
          <h1>内容审核</h1>
          <p>课程视频、招聘职位与非遗教学视频共用同一审核队列。</p>
        </div>
      </div>
      <dl class="review-header__summary">
        <div>
          <dt>待处理</dt>
          <dd class="ark-data">{{ totalPending }}</dd>
        </div>
        <div>
          <dt>当前显示</dt>
          <dd class="ark-data">{{ filteredItems.length }}</dd>
        </div>
      </dl>
    </header>

    <div
      class="review-filter"
      role="group"
      aria-label="按内容类型筛选审核队列"
      data-test="admin-review-filter"
    >
      <button
        type="button"
        data-test="admin-review-filter-all"
        :class="{ 'is-active': activeFilter === 'all' }"
        :aria-pressed="activeFilter === 'all'"
        @click="activeFilter = 'all'"
      >
        <span>全部</span>
        <strong class="ark-data">{{ totalPending }}</strong>
      </button>
      <button
        v-for="option in contentTypeOptions"
        :key="option.value"
        type="button"
        :data-test="`admin-review-filter-${option.value}`"
        :class="{ 'is-active': activeFilter === option.value }"
        :aria-pressed="activeFilter === option.value"
        @click="activeFilter = option.value"
      >
        <span>{{ option.label }}</span>
        <strong
          class="ark-data"
          :data-test="`admin-review-count-${option.value}`"
        >
          {{ store.reviewCounts[option.value] }}
        </strong>
      </button>
    </div>

    <p
      v-if="actionMessage"
      class="review-message"
      data-test="admin-review-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ actionMessage }}
    </p>

    <div
      v-if="store.reviewError"
      class="review-error"
      data-test="admin-review-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.reviewError }}</span>
      <button
        type="button"
        data-test="admin-review-retry"
        :disabled="store.reviewLoading"
        @click="store.loadReviewQueue()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="review-registry" aria-labelledby="review-registry-title">
      <header class="review-registry__heading">
        <h2 id="review-registry-title">审核队列</h2>
        <span class="ark-data">{{ filteredItems.length }} 条</span>
      </header>

      <div
        v-if="store.reviewLoading && store.reviewItems.length === 0"
        class="review-state"
        data-test="admin-review-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载审核队列
      </div>

      <div
        v-else-if="filteredItems.length === 0"
        class="review-state review-state--empty"
        data-test="admin-review-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无待审核内容</span>
      </div>

      <div v-else class="review-table-wrap">
        <table class="review-table">
          <thead>
            <tr>
              <th scope="col">内容</th>
              <th scope="col">类型</th>
              <th scope="col">状态</th>
              <th scope="col">版本</th>
              <th scope="col">提交者</th>
              <th scope="col">更新时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredItems"
              :key="`${item.content_type}:${item.content_id}`"
              data-test="admin-review-row"
              :data-content-type="item.content_type"
              :data-content-id="item.content_id"
            >
              <td data-label="内容">
                <div class="review-table__title">
                  <strong>{{ item.title || item.content_id }}</strong>
                  <span class="ark-data">ID {{ item.content_id }}</span>
                </div>
              </td>
              <td data-label="类型">{{ contentLabel(item.content_type) }}</td>
              <td data-label="状态">
                <span
                  class="review-status"
                  :class="`is-${item.review_status}`"
                  data-test="admin-review-status"
                >
                  {{ statusLabel(item.review_status) }}
                </span>
              </td>
              <td data-label="版本">
                <span class="ark-data">
                  {{ item.version === null ? '未知' : `版本 ${item.version}` }}
                </span>
              </td>
              <td data-label="提交者">{{ submitterLabel(item) }}</td>
              <td data-label="更新时间">
                <time
                  class="ark-data"
                  :datetime="item.updated_at || undefined"
                >
                  {{ formatUpdatedAt(item.updated_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div
                  v-if="
                    item.review_status === 'pending' &&
                    item.version !== null
                  "
                  class="review-actions"
                >
                  <button
                    type="button"
                    data-test="admin-review-approve"
                    :aria-label="`通过审核：${item.title || item.content_id}`"
                    :title="`通过审核：${item.title || item.content_id}`"
                    :disabled="store.reviewActionLoading"
                    @click="openApprove(item)"
                  >
                    <Check :size="16" aria-hidden="true" />
                    通过
                  </button>
                  <button
                    type="button"
                    data-test="admin-review-reject"
                    :aria-label="`驳回审核：${item.title || item.content_id}`"
                    :title="`驳回审核：${item.title || item.content_id}`"
                    :disabled="store.reviewActionLoading"
                    @click="openReject(item)"
                  >
                    <X :size="16" aria-hidden="true" />
                    驳回
                  </button>
                </div>
                <span v-else class="review-processed">已处理</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div
      v-if="approveCandidate"
      class="review-dialog-backdrop"
      data-test="admin-review-approve-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="review-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-approve-title"
      >
        <header>
          <h2 id="review-approve-title">确认通过审核</h2>
          <button
            type="button"
            aria-label="关闭通过审核对话框"
            title="关闭"
            :disabled="store.reviewActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          「{{ approveCandidate.title || approveCandidate.content_id }}」
          通过后将进入学员可见位置。
        </p>
        <div class="review-dialog__actions">
          <button
            type="button"
            data-test="admin-review-confirm-approve"
            :disabled="store.reviewActionLoading"
            @click="confirmApprove"
          >
            <Check :size="16" aria-hidden="true" />
            {{ store.reviewActionLoading ? '正在处理' : '确认通过' }}
          </button>
          <button
            type="button"
            :disabled="store.reviewActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>

    <div
      v-if="rejectCandidate"
      class="review-dialog-backdrop"
      data-test="admin-review-reject-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="review-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-reject-title"
      >
        <header>
          <h2 id="review-reject-title">驳回审核</h2>
          <button
            type="button"
            aria-label="关闭驳回审核对话框"
            title="关闭"
            :disabled="store.reviewActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          驳回「{{ rejectCandidate.title || rejectCandidate.content_id }}」时，
          必须填写可执行的修改意见。
        </p>
        <label class="review-opinion">
          <span>驳回意见</span>
          <textarea
            v-model="opinion"
            data-test="admin-review-opinion"
            maxlength="500"
            rows="5"
            placeholder="说明需要补充或修改的内容"
          />
        </label>
        <div class="review-opinion__meta">
          <span
            data-test="admin-review-opinion-count"
            class="ark-data"
          >
            {{ opinion.length }} / 500
          </span>
          <span v-if="!trimmedOpinion.length">去除空白后不能为空</span>
        </div>
        <div class="review-dialog__actions">
          <button
            type="button"
            data-test="admin-review-confirm-reject"
            :disabled="!canSubmitReject || store.reviewActionLoading"
            @click="confirmReject"
          >
            <X :size="16" aria-hidden="true" />
            {{ store.reviewActionLoading ? '正在处理' : '确认驳回' }}
          </button>
          <button
            type="button"
            :disabled="store.reviewActionLoading"
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
.admin-review-page {
  min-width: 0;
  color: var(--ark-paper);
}

.review-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, 0.58fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.review-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.review-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.review-header__identity > div {
  min-width: 0;
}

.review-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.review-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.review-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.review-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 20px 22px;
  background: var(--ark-surface-1);
}

.review-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.review-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 2rem;
  line-height: 1;
}

.review-filter {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.review-filter button {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: left;
}

.review-filter button:hover,
.review-filter button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.review-filter button.is-active {
  box-shadow: inset 0 -2px 0 var(--ark-signal);
  color: var(--ark-signal);
}

.review-filter span {
  min-width: 0;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.review-filter strong {
  color: inherit;
  font-size: 1.2rem;
}

.review-message,
.review-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.review-message {
  color: var(--ark-state);
}

.review-message svg,
.review-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.review-message,
.review-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.review-error button {
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

.review-registry {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.review-registry__heading {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.review-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.review-registry__heading span {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.review-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.review-state--empty {
  flex-direction: column;
}

.review-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.review-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.review-table th,
.review-table td {
  min-width: 0;
  padding: 14px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.review-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
}

.review-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.review-table th:nth-child(1) {
  width: 21%;
}

.review-table th:nth-child(2) {
  width: 13%;
}

.review-table th:nth-child(3) {
  width: 10%;
}

.review-table th:nth-child(4) {
  width: 10%;
}

.review-table th:nth-child(5) {
  width: 14%;
}

.review-table th:nth-child(6) {
  width: 17%;
}

.review-table th:nth-child(7) {
  width: 15%;
}

.review-table tbody tr:last-child td {
  border-bottom: 0;
}

.review-table__title {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.review-table__title strong {
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.review-table__title span,
.review-table time,
.review-processed {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.review-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.review-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.review-status.is-pending {
  color: var(--ark-signal);
}

.review-status.is-approved {
  color: var(--ark-state);
}

.review-status.is-rejected,
.review-status.is-offline {
  color: var(--ark-muted);
}

.review-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.review-actions button,
.review-dialog__actions button {
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

.review-actions button {
  flex: 1 1 72px;
}

.review-actions button:first-child,
.review-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.review-actions button:hover:not(:disabled),
.review-dialog__actions button:hover:not(:disabled),
.review-error button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.review-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(5 6 7 / 0.72);
}

.review-dialog {
  width: min(100%, 560px);
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  box-shadow: 12px 14px 40px rgb(0 0 0 / 0.28);
}

.review-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.review-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.review-dialog header button {
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

.review-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.review-opinion {
  display: grid;
  gap: 7px;
  padding: 16px 18px 0;
}

.review-opinion > span,
.review-opinion__meta {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.review-opinion textarea {
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

.review-opinion textarea:hover {
  border-color: var(--ark-signal);
}

.review-opinion textarea::placeholder {
  color: var(--ark-muted);
}

.review-opinion__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 18px 0;
}

.review-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.review-dialog__actions button {
  min-width: 108px;
}

.admin-review-page :is(button, textarea):focus-visible {
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
  .review-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .review-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .review-filter {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .review-table-wrap {
    overflow-x: visible;
  }

  .review-table,
  .review-table tbody {
    display: block;
  }

  .review-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .review-table tbody {
    display: grid;
    gap: 1px;
    background: var(--ark-line);
  }

  .review-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .review-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .review-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }

  .review-table td:last-child {
    border-bottom: 0;
  }

  .review-table__title {
    justify-items: end;
    text-align: right;
  }

  .review-actions {
    justify-content: flex-end;
  }
}

@media (max-width: 520px) {
  .review-header__identity {
    padding: 21px 16px;
  }

  .review-header__identity h1 {
    font-size: 2rem;
  }

  .review-filter {
    grid-template-columns: minmax(0, 1fr);
  }

  .review-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .review-table__title {
    justify-items: start;
    text-align: left;
  }

  .review-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .review-dialog-backdrop {
    padding: 10px;
  }

  .review-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .review-dialog__actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
