<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
  approveAdminReview,
  getAdminReviews,
  rejectAdminReview,
  revokeAdminReview,
  type AdminReview,
  type ReviewContentType,
  type ReviewCounts,
  type ReviewStatus,
} from "@/api/admin";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import { resolveMediaUrl } from "@/shared/url";

type FeedbackKind = "info" | "success" | "error";
type StatusFilter = ReviewStatus | "all";

interface DetailLine {
  label: string;
  value: string;
}

const STATUS_TABS: Array<{ value: StatusFilter; label: string }> = [
  { value: "pending", label: "待审核" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已驳回" },
  { value: "all", label: "全部" },
];

const CONTENT_TYPES: Array<{
  value: ReviewContentType | "";
  label: string;
}> = [
  { value: "", label: "全部类型" },
  { value: "course", label: "课程" },
  { value: "job", label: "岗位" },
  { value: "success_case", label: "成功案例" },
  { value: "model_3d", label: "3D 模型" },
];

const reviews = ref<AdminReview[]>([]);
const counts = ref<ReviewCounts>({
  pending: 0,
  approved: 0,
  rejected: 0,
});
const status = ref<StatusFilter>("pending");
const contentType = ref<ReviewContentType | "">("");
const sort = ref<"modified" | "created">("modified");
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: FeedbackKind; message: string } | null>(null);
const busyId = ref<number | null>(null);
const rejectTarget = ref<AdminReview | null>(null);
const rejectReason = ref("");
const rejectError = ref("");
const revokeTarget = ref<AdminReview | null>(null);
let loadSequence = 0;

const emptyTitle = computed(() => {
  if (status.value === "approved") return "暂无已通过记录";
  if (status.value === "rejected") return "暂无已驳回记录";
  if (status.value === "all") return "暂无审核记录";
  return "暂无待审核内容";
});

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function typeLabel(value: string): string {
  return CONTENT_TYPES.find((item) => item.value === value)?.label ?? value;
}

function statusLabel(value: string): string {
  if (value === "approved") return "已通过";
  if (value === "rejected") return "已驳回";
  return "待审核";
}

function countFor(value: StatusFilter): number | null {
  if (value === "all") return null;
  return counts.value[value];
}

function textValue(value: unknown): string {
  if (Array.isArray(value)) return value.join("、");
  return typeof value === "string" ? value : "";
}

function reviewTitle(review: AdminReview): string {
  const detail = review.detail;
  return (
    textValue(detail?.title) ||
    textValue(detail?.name) ||
    `${typeLabel(review.content_type)} #${review.content_id}`
  );
}

function detailLines(review: AdminReview): DetailLine[] {
  const detail = review.detail;
  if (!detail) return [];
  const lines: DetailLine[] = [];
  const add = (label: string, value: unknown) => {
    const text = textValue(value);
    if (text) lines.push({ label, value: text });
  };

  if (review.content_type === "job") {
    add("公司", detail.company);
    add("薪资", detail.salary);
    add("地点", detail.location);
    add("任职要求", detail.requirements);
  } else if (review.content_type === "success_case") {
    add("地区", detail.region || detail.location);
    add("概述", detail.description);
  } else if (review.content_type === "model_3d") {
    add("技艺", detail.craft_type);
    add("文件", detail.file_name);
  }
  add("说明", detail.description);
  return lines;
}

function modelFileUrl(review: AdminReview): string {
  return review.content_type === "model_3d"
    ? resolveMediaUrl(textValue(review.detail?.file_path))
    : "";
}

async function loadReviews(): Promise<void> {
  const sequence = ++loadSequence;
  loading.value = true;
  loadError.value = "";
  try {
    const response = await getAdminReviews({
      status: status.value,
      contentType: contentType.value,
      sort: sort.value,
    });
    if (sequence !== loadSequence) return;
    reviews.value = response.reviews;
    counts.value = response.counts;
  } catch (error) {
    if (sequence !== loadSequence) return;
    reviews.value = [];
    loadError.value = errorMessage(error, "审核列表加载失败");
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

async function approve(review: AdminReview): Promise<void> {
  if (busyId.value !== null) return;
  busyId.value = review.id;
  feedback.value = null;
  try {
    const response = await approveAdminReview(review.id);
    feedback.value = { kind: "success", message: response.message };
    await loadReviews();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(error, "审核通过失败"),
    };
  } finally {
    busyId.value = null;
  }
}

function openReject(review: AdminReview): void {
  rejectTarget.value = review;
  rejectReason.value = "";
  rejectError.value = "";
}

function closeReject(): void {
  if (busyId.value !== null) return;
  rejectTarget.value = null;
  rejectReason.value = "";
  rejectError.value = "";
}

async function confirmReject(): Promise<void> {
  const target = rejectTarget.value;
  const reason = rejectReason.value.trim();
  if (!target) return;
  if (!reason) {
    rejectError.value = "请填写驳回理由，提交者需要知道如何修改";
    return;
  }
  busyId.value = target.id;
  rejectError.value = "";
  try {
    const response = await rejectAdminReview(target.id, reason);
    rejectTarget.value = null;
    feedback.value = { kind: "success", message: response.message };
    await loadReviews();
  } catch (error) {
    rejectError.value = errorMessage(error, "驳回失败");
  } finally {
    busyId.value = null;
  }
}

function openRevoke(review: AdminReview): void {
  revokeTarget.value = review;
}

function closeRevoke(): void {
  if (busyId.value !== null) return;
  revokeTarget.value = null;
}

async function confirmRevoke(): Promise<void> {
  const target = revokeTarget.value;
  if (!target) return;
  busyId.value = target.id;
  try {
    const response = await revokeAdminReview(target.id);
    revokeTarget.value = null;
    feedback.value = { kind: "success", message: response.message };
    await loadReviews();
  } catch (error) {
    feedback.value = {
      kind: "error",
      message: errorMessage(error, "撤销审核失败"),
    };
  } finally {
    busyId.value = null;
  }
}

watch([status, contentType, sort], () => {
  void loadReviews();
});

onMounted(loadReviews);
</script>

<template>
  <section class="bo-page">
    <header class="bo-page-header">
      <div>
        <p>平台治理</p>
        <h1 data-testid="backoffice-page-title">
          内容审核
        </h1>
        <span>课程、岗位、案例与 3D 模型通过审核后才对学员公开。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadReviews"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新审核
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="admin-reviews-feedback"
    />

    <BackofficeCard flush>
      <div class="admin-review-toolbar">
        <div
          class="admin-review-tabs"
          role="group"
          aria-label="审核状态"
        >
          <button
            v-for="tab in STATUS_TABS"
            :key="tab.value"
            type="button"
            class="admin-review-tab"
            :class="{ 'is-active': status === tab.value }"
            :data-testid="`admin-review-status-${tab.value}`"
            :aria-pressed="status === tab.value"
            @click="status = tab.value"
          >
            {{ tab.label }}
            <span v-if="countFor(tab.value) !== null">
              {{ countFor(tab.value) }}
            </span>
          </button>
        </div>

        <div class="admin-review-filters">
          <label class="bo-field">
            <span>内容类型</span>
            <select v-model="contentType">
              <option
                v-for="item in CONTENT_TYPES"
                :key="item.value || 'all'"
                :value="item.value"
              >
                {{ item.label }}
              </option>
            </select>
          </label>
          <label class="bo-field">
            <span>排序</span>
            <select v-model="sort">
              <option value="modified">
                修改时间
              </option>
              <option value="created">
                提交时间
              </option>
            </select>
          </label>
        </div>
      </div>

      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在读取审核队列"
      />
      <div
        v-else-if="loadError"
        data-testid="admin-reviews-error"
      >
        <BackofficeState
          kind="error"
          title="审核列表加载失败"
          :detail="loadError"
        >
          <button
            type="button"
            class="bo-button"
            @click="loadReviews"
          >
            重试
          </button>
        </BackofficeState>
      </div>
      <div
        v-else-if="!reviews.length"
        data-testid="admin-reviews-empty"
      >
        <BackofficeState
          kind="empty"
          :title="emptyTitle"
          detail="当前筛选条件下没有需要处理的记录。"
        />
      </div>

      <div
        v-else
        class="admin-review-list"
      >
        <article
          v-for="review in reviews"
          :key="review.id"
          class="admin-review-card"
          data-testid="admin-review-row"
          :data-review-id="review.id"
          :data-content-type="review.content_type"
        >
          <header class="admin-review-head">
            <div class="admin-review-tags">
              <span class="admin-review-type">{{ typeLabel(review.content_type) }}</span>
              <span
                class="admin-review-status"
                :class="`is-${review.status}`"
              >
                {{ statusLabel(review.status) }}
              </span>
              <span
                v-if="review.is_self_reviewed"
                class="admin-review-self"
                title="提交者与审核人是同一账号，该记录不含第三方把关"
              >
                自提自审
              </span>
            </div>
            <time>{{ review.reviewed_at || review.created_at }}</time>
          </header>

          <h2>{{ reviewTitle(review) }}</h2>
          <dl
            v-if="detailLines(review).length"
            class="admin-review-detail"
          >
            <template
              v-for="line in detailLines(review)"
              :key="line.label"
            >
              <dt>{{ line.label }}</dt>
              <dd>{{ line.value }}</dd>
            </template>
          </dl>
          <p
            v-if="review.review_comment"
            class="admin-review-reason"
          >
            <strong>驳回理由：</strong>{{ review.review_comment }}
          </p>
          <p class="admin-review-meta">
            提交者 {{ review.submitter_id || "未知" }}
            <span v-if="review.reviewed_by"> · 审核人 {{ review.reviewed_by }}</span>
            <span v-if="review.is_self_reviewed"> · 本条记录为自提自审，不构成第三方背书</span>
          </p>

          <footer class="admin-review-actions">
            <a
              v-if="modelFileUrl(review)"
              class="bo-button is-small is-secondary"
              :href="modelFileUrl(review)"
              target="_blank"
              rel="noopener"
            >
              打开模型文件
            </a>
            <template v-if="review.status === 'pending'">
              <button
                type="button"
                class="bo-button is-small is-success"
                :disabled="busyId !== null"
                @click="approve(review)"
              >
                通过
              </button>
              <button
                type="button"
                class="bo-button is-small is-danger"
                :disabled="busyId !== null"
                @click="openReject(review)"
              >
                驳回
              </button>
            </template>
            <button
              v-else
              type="button"
              class="bo-button is-small is-secondary"
              :disabled="busyId !== null"
              @click="openRevoke(review)"
            >
              撤销审核
            </button>
          </footer>
        </article>
      </div>
    </BackofficeCard>

    <Teleport to="body">
      <div
        v-if="rejectTarget"
        class="bo-modal-overlay"
        @click.self="closeReject"
      >
        <form
          class="bo-modal"
          data-testid="admin-review-reject-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="驳回内容"
          @submit.prevent="confirmReject"
        >
          <header class="bo-modal-head">
            <div>
              <p>审核结论</p>
              <h2>驳回 {{ reviewTitle(rejectTarget) }}</h2>
            </div>
            <button
              type="button"
              class="bo-icon-button"
              aria-label="关闭"
              @click="closeReject"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="bo-modal-body">
            <BackofficeFeedback
              v-if="rejectError"
              kind="error"
              :message="rejectError"
            />
            <label class="bo-field">
              <span>驳回理由</span>
              <textarea
                v-model="rejectReason"
                rows="4"
                required
                placeholder="说明需要修改的具体内容"
              />
            </label>
          </div>
          <footer class="bo-modal-actions">
            <button
              type="button"
              class="bo-button is-secondary"
              :disabled="busyId !== null"
              @click="closeReject"
            >
              取消
            </button>
            <button
              type="submit"
              class="bo-button is-danger"
              :disabled="busyId !== null"
            >
              {{ busyId !== null ? "提交中..." : "确认驳回" }}
            </button>
          </footer>
        </form>
      </div>

      <div
        v-if="revokeTarget"
        class="bo-modal-overlay"
        @click.self="closeRevoke"
      >
        <div
          class="bo-modal is-confirm"
          data-testid="admin-review-confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="撤销审核"
        >
          <header class="bo-modal-head">
            <div>
              <p>安全确认</p>
              <h2>撤销审核</h2>
            </div>
          </header>
          <div class="bo-modal-body">
            <p class="bo-confirm-copy">
              确定撤销「{{ reviewTitle(revokeTarget) }}」的审核结论？内容会退回待审核并立即从公开页面下架。
            </p>
          </div>
          <footer class="bo-modal-actions">
            <button
              type="button"
              class="bo-button is-secondary"
              :disabled="busyId !== null"
              @click="closeRevoke"
            >
              取消
            </button>
            <button
              type="button"
              class="bo-button is-danger"
              :disabled="busyId !== null"
              @click="confirmRevoke"
            >
              {{ busyId !== null ? "处理中..." : "确认撤销" }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.admin-review-toolbar {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--bo-card-border);
}

.admin-review-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.admin-review-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 6px 13px;
  border: 1px solid var(--bo-input-border);
  border-radius: 999px;
  background: var(--bo-input-bg);
  color: var(--bo-muted);
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
}

.admin-review-tab span {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--bo-accent-soft);
  color: var(--bo-accent-strong);
  font-size: 0.72rem;
  text-align: center;
}

.admin-review-tab.is-active {
  border-color: var(--bo-accent);
  background: var(--bo-accent);
  color: #fff;
}

.admin-review-tab.is-active span {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.admin-review-filters {
  display: flex;
  gap: 10px;
}

.admin-review-list {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.admin-review-card {
  padding: 16px;
  border: 1px solid var(--bo-card-border);
  border-radius: 12px;
  background: var(--bo-card-bg);
}

.admin-review-head,
.admin-review-actions,
.admin-review-tags {
  display: flex;
  align-items: center;
}

.admin-review-head {
  justify-content: space-between;
  gap: 12px;
}

.admin-review-head time {
  color: var(--bo-muted);
  font-size: 0.74rem;
  white-space: nowrap;
}

.admin-review-tags {
  flex-wrap: wrap;
  gap: 7px;
}

.admin-review-type,
.admin-review-status,
.admin-review-self {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
}

.admin-review-type {
  background: var(--bo-accent-soft);
  color: var(--bo-accent-strong);
}

.admin-review-status.is-pending {
  background: #fff2cf;
  color: #835d00;
}

.admin-review-status.is-approved {
  background: #dff2e6;
  color: #1f6b42;
}

.admin-review-status.is-rejected {
  background: #fde4e1;
  color: #9b2f27;
}

.admin-review-self {
  background: #ece6cf;
  color: #6f5a16;
}

.admin-review-card h2 {
  margin: 12px 0 8px;
  font-size: 1rem;
}

.admin-review-detail {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 5px 12px;
  margin: 0 0 10px;
  font-size: 0.84rem;
}

.admin-review-detail dt {
  color: var(--bo-muted);
}

.admin-review-detail dd {
  margin: 0;
  color: var(--bo-text);
}

.admin-review-reason {
  margin: 10px 0;
  padding: 9px 11px;
  border-left: 3px solid var(--bo-danger);
  background: color-mix(in srgb, var(--bo-danger) 7%, transparent);
  color: var(--bo-text);
  font-size: 0.82rem;
}

.admin-review-meta {
  margin: 8px 0 0;
  color: var(--bo-muted);
  font-size: 0.74rem;
}

.admin-review-actions {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

@media (max-width: 760px) {
  .admin-review-toolbar,
  .admin-review-filters {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
