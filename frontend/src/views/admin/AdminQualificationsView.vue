<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  adminLicenseUrl,
  fetchLicenseObjectUrl,
  getAdminQualifications,
  reviewQualification,
  type AdminQualification,
  type AdminQualificationList,
} from "@/api/qualification";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

type Tab = "pending" | "approved" | "rejected" | "all";

const tabs: { key: Tab; label: string }[] = [
  { key: "pending", label: "待审核" },
  { key: "approved", label: "已通过" },
  { key: "rejected", label: "已驳回" },
  { key: "all", label: "全部" },
];

const activeTab = ref<Tab>("pending");
const list = ref<AdminQualificationList | null>(null);
const loading = ref(true);
const error = ref("");
const actionError = ref("");
const busyId = ref(0);

const rejectTarget = ref<AdminQualification | null>(null);
const rejectReason = ref("");
const customReason = ref("");

const licensePreviewId = ref(0);
const licensePreviewUrl = ref("");
const licenseLoading = ref(false);

const finalReason = computed(() =>
  (rejectReason.value === "__custom__" ? customReason.value : rejectReason.value).trim(),
);

async function load(tab: Tab = activeTab.value): Promise<void> {
  activeTab.value = tab;
  loading.value = true;
  error.value = "";
  actionError.value = "";
  try {
    list.value = await getAdminQualifications(tab);
  } catch (requestError) {
    list.value = null;
    error.value =
      requestError instanceof ApiError ? requestError.message : "认证队列加载失败";
  } finally {
    loading.value = false;
  }
}

async function approve(item: AdminQualification): Promise<void> {
  actionError.value = "";
  busyId.value = item.id;
  try {
    await reviewQualification(item.id, "approved", "");
    await load();
  } catch (requestError) {
    actionError.value =
      requestError instanceof ApiError ? requestError.message : "审核失败";
  } finally {
    busyId.value = 0;
  }
}

function openReject(item: AdminQualification): void {
  rejectTarget.value = item;
  rejectReason.value = list.value?.reject_reasons[0] ?? "__custom__";
  customReason.value = "";
  actionError.value = "";
}

async function confirmReject(): Promise<void> {
  if (!rejectTarget.value) return;
  if (!finalReason.value) {
    actionError.value = "请填写驳回理由";
    return;
  }
  busyId.value = rejectTarget.value.id;
  actionError.value = "";
  try {
    await reviewQualification(rejectTarget.value.id, "rejected", finalReason.value);
    rejectTarget.value = null;
    await load();
  } catch (requestError) {
    actionError.value =
      requestError instanceof ApiError ? requestError.message : "驳回失败";
  } finally {
    busyId.value = 0;
  }
}

async function toggleLicense(item: AdminQualification): Promise<void> {
  if (licensePreviewId.value === item.id) {
    revokeLicense();
    return;
  }
  revokeLicense();
  licenseLoading.value = true;
  try {
    licensePreviewUrl.value = await fetchLicenseObjectUrl(adminLicenseUrl(item.id));
    licensePreviewId.value = item.id;
  } catch (requestError) {
    actionError.value =
      requestError instanceof ApiError ? requestError.message : "证件照打开失败";
  } finally {
    licenseLoading.value = false;
  }
}

function revokeLicense(): void {
  if (licensePreviewUrl.value) URL.revokeObjectURL(licensePreviewUrl.value);
  licensePreviewUrl.value = "";
  licensePreviewId.value = 0;
}

function isPdf(item: AdminQualification): boolean {
  return (item.license_name || "").toLowerCase().endsWith(".pdf");
}

onMounted(() => load());
onBeforeUnmount(revokeLicense);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>企业身份</p>
        <h1>企业认证</h1>
        <span>核定企业提交的资质材料。驳回必须填写理由，企业端会原样看到。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="load()"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <div class="qual-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="qual-tab"
        :class="{ active: activeTab === tab.key }"
        @click="load(tab.key)"
      >
        {{ tab.label }}
        <span
          v-if="tab.key === 'pending' && list"
          class="qual-tab-count"
        >{{ list.pending_count }}</span>
      </button>
    </div>

    <p
      v-if="actionError"
      class="qual-error"
      role="alert"
    >
      {{ actionError }}
    </p>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取企业认证队列"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="队列加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="load()"
      >
        重试
      </button>
    </BackofficeState>
    <BackofficeState
      v-else-if="!list || list.items.length === 0"
      kind="empty"
      title="这个分组暂时没有记录"
    />

    <template v-else>
      <BackofficeCard
        v-for="item in list?.items ?? []"
        :key="item.id"
        :title="item.company_name"
        :description="`${item.user_id} · 提交于 ${item.submitted_at}`"
      >
      <template #actions>
        <span
          class="qual-badge"
          :class="`is-${item.status}`"
        >{{ item.status_label }}</span>
      </template>

      <dl class="qual-facts">
        <div>
          <dt>统一社会信用代码</dt>
          <dd>{{ item.credit_code_masked }}</dd>
        </div>
        <div>
          <dt>负责人</dt>
          <dd>{{ item.legal_person || "未填写" }}</dd>
        </div>
        <div>
          <dt>联系电话</dt>
          <dd>{{ item.contact_phone || item.applicant_phone || "未填写" }}</dd>
        </div>
        <div>
          <dt>注册地址</dt>
          <dd>{{ item.address || "未填写" }}</dd>
        </div>
        <div>
          <dt>账号公司名</dt>
          <dd>
            {{ item.account_company_name || "未填写" }}
            <span
              v-if="item.account_company_name && !item.name_matches_account"
              class="qual-warn"
            >与提交名称不一致</span>
          </dd>
        </div>
        <div v-if="item.reviewed_at">
          <dt>审核时间</dt>
          <dd>{{ item.reviewed_at }}（{{ item.reviewed_by }}）</dd>
        </div>
        <div v-if="item.expires_at">
          <dt>有效期至</dt>
          <dd>{{ item.expires_at }}</dd>
        </div>
      </dl>

      <p
        v-if="item.review_comment"
        class="qual-note"
      >
        审核意见：{{ item.review_comment }}
      </p>

      <div class="qual-actions">
        <button
          v-if="item.has_license"
          type="button"
          class="backoffice-button is-secondary"
          :disabled="licenseLoading"
          @click="toggleLicense(item)"
        >
          {{ licensePreviewId === item.id ? "收起证件照" : "查看证件照" }}
        </button>
        <span
          v-else
          class="qual-warn"
        >未上传证件照</span>

        <template v-if="item.status === 'pending'">
          <button
            type="button"
            class="backoffice-button"
            :disabled="busyId === item.id"
            @click="approve(item)"
          >
            通过认证
          </button>
          <button
            type="button"
            class="backoffice-button is-secondary"
            :disabled="busyId === item.id"
            @click="openReject(item)"
          >
            驳回
          </button>
        </template>
      </div>

      <div
        v-if="licensePreviewId === item.id && licensePreviewUrl"
        class="qual-license"
      >
        <a
          v-if="isPdf(item)"
          :href="licensePreviewUrl"
          target="_blank"
          rel="noopener noreferrer"
        >在新窗口打开 PDF</a>
        <img
          v-else
          :src="licensePreviewUrl"
          alt="营业执照"
        >
      </div>

      <form
        v-if="rejectTarget?.id === item.id"
        class="qual-reject-form"
        @submit.prevent="confirmReject"
      >
        <label for="reject-reason">驳回理由</label>
        <select
          id="reject-reason"
          v-model="rejectReason"
        >
          <option
            v-for="reason in list?.reject_reasons ?? []"
            :key="reason"
            :value="reason"
          >
            {{ reason }}
          </option>
          <option value="__custom__">
            其他（自己填写）
          </option>
        </select>
        <textarea
          v-if="rejectReason === '__custom__'"
          v-model="customReason"
          rows="3"
          placeholder="写清楚需要企业补充或更正什么"
        />
        <div class="qual-actions">
          <button
            type="submit"
            class="backoffice-button"
            :disabled="busyId === item.id"
          >
            确认驳回
          </button>
          <button
            type="button"
            class="backoffice-button is-secondary"
            @click="rejectTarget = null"
          >
            取消
          </button>
        </div>
      </form>
      </BackofficeCard>
    </template>
  </section>
</template>

<style scoped>
.qual-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}

.qual-tab {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--bo-muted);
  padding: 6px 16px;
  cursor: pointer;
}

.qual-tab.active {
  border-color: var(--bo-accent);
  color: var(--bo-accent-strong);
  background: var(--bo-accent-soft);
}

.qual-tab-count {
  margin-left: 6px;
  font-size: 0.78rem;
}

.qual-badge {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 0.78rem;
  background: var(--surface-muted);
  color: var(--bo-muted);
}

.qual-badge.is-approved {
  background: var(--state-success-bg);
  color: var(--bo-success);
}

.qual-badge.is-rejected {
  background: var(--state-error-bg);
  color: var(--bo-danger);
}

.qual-badge.is-pending {
  background: var(--state-info-bg);
  color: var(--state-info-text);
}

.qual-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 24px;
  margin: 14px 0 0;
}

.qual-facts dt {
  font-size: 0.78rem;
  color: var(--bo-muted);
}

.qual-facts dd {
  margin: 2px 0 0;
  color: var(--bo-text);
}

.qual-warn {
  margin-left: 8px;
  font-size: 0.78rem;
  color: var(--bo-danger);
}

.qual-note {
  margin: 12px 0 0;
  font-size: 0.85rem;
  color: var(--bo-muted);
}

.qual-error {
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  background: var(--state-error-bg);
  color: var(--bo-danger);
  font-size: 0.88rem;
}

.qual-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

.qual-license img {
  max-width: 100%;
  max-height: 420px;
  margin-top: 12px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-default);
}

.qual-reject-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
  padding: 14px;
  border-radius: var(--radius-sm);
  background: var(--surface-muted);
}

.qual-reject-form label {
  font-size: 0.82rem;
  color: var(--bo-muted);
}

.qual-reject-form select,
.qual-reject-form textarea {
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--bo-input-border);
  background: var(--bo-input-bg);
  color: var(--bo-text);
}
</style>
