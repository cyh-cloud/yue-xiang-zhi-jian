<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  enterpriseLicenseUrl,
  fetchLicenseObjectUrl,
  getQualification,
  submitQualification,
  withdrawQualification,
  type QualificationStatus,
} from "@/api/qualification";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";
import { useSessionStore } from "@/stores/session";

const session = useSessionStore();

const loading = ref(true);
const error = ref("");
const status = ref<QualificationStatus | null>(null);

const companyName = ref("");
const creditCode = ref("");
const legalPerson = ref("");
const contactPhone = ref("");
const address = ref("");
const industry = ref("");
const companySize = ref("");
const licenseFile = ref<File | null>(null);

const submitting = ref(false);
const withdrawing = ref(false);
const submitError = ref("");
const submitMessage = ref("");

const licensePreview = ref("");
const licenseLoading = ref(false);

const canSubmit = computed(() => {
  const state = status.value?.status;
  return state === "none" || state === "rejected" || state === "expired"
    || state === "withdrawn";
});

const stateTone = computed(() => {
  switch (status.value?.status) {
    case "approved":
      return "is-approved";
    case "pending":
      return "is-pending";
    case "rejected":
      return "is-rejected";
    case "expired":
      return "is-rejected";
    default:
      return "is-idle";
  }
});

function prefill(): void {
  const record = status.value?.record;
  companyName.value = record?.company_name || session.user?.company_name || "";
  legalPerson.value = record?.legal_person || session.user?.name || "";
  contactPhone.value = record?.contact_phone || session.user?.phone || "";
  address.value = record?.address || session.user?.region || "";
  industry.value = record?.industry || "";
  companySize.value = record?.company_size || "";
  creditCode.value = "";
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    status.value = await getQualification();
    prefill();
  } catch (requestError) {
    status.value = null;
    error.value =
      requestError instanceof ApiError
        ? requestError.message
        : "资质状态加载失败";
  } finally {
    loading.value = false;
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  licenseFile.value = input.files?.[0] ?? null;
}

async function submit(): Promise<void> {
  submitError.value = "";
  submitMessage.value = "";
  if (!companyName.value.trim() || !creditCode.value.trim()) {
    submitError.value = "请填写企业名称与统一社会信用代码";
    return;
  }
  submitting.value = true;
  try {
    const response = await submitQualification({
      company_name: companyName.value,
      credit_code: creditCode.value,
      legal_person: legalPerson.value,
      contact_phone: contactPhone.value,
      address: address.value,
      industry: industry.value,
      company_size: companySize.value,
      license: licenseFile.value,
    });
    submitMessage.value = response.message;
    licenseFile.value = null;
    await load();
  } catch (requestError) {
    submitError.value =
      requestError instanceof ApiError ? requestError.message : "提交失败，请重试";
  } finally {
    submitting.value = false;
  }
}

async function withdraw(): Promise<void> {
  if (withdrawing.value) return;
  withdrawing.value = true;
  submitError.value = "";
  submitMessage.value = "";
  try {
    const response = await withdrawQualification();
    submitMessage.value = response.message;
    await load();
  } catch (requestError) {
    submitError.value =
      requestError instanceof ApiError ? requestError.message : "撤回失败";
  } finally {
    withdrawing.value = false;
  }
}

async function previewLicense(): Promise<void> {  if (!status.value?.record?.has_license) return;
  licenseLoading.value = true;
  try {
    if (licensePreview.value) {
      URL.revokeObjectURL(licensePreview.value);
      licensePreview.value = "";
      return;
    }
    licensePreview.value = await fetchLicenseObjectUrl(enterpriseLicenseUrl);
  } catch (requestError) {
    submitError.value =
      requestError instanceof ApiError ? requestError.message : "证件照打开失败";
  } finally {
    licenseLoading.value = false;
  }
}

const licenseIsPdf = computed(
  () => (status.value?.record?.license_name || "").toLowerCase().endsWith(".pdf"),
);

onMounted(load);
onBeforeUnmount(() => {
  if (licensePreview.value) URL.revokeObjectURL(licensePreview.value);
});
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>企业身份</p>
        <h1>资质认证</h1>
        <span>提交营业执照与统一社会信用代码，审核通过后获得认证标识并解除岗位发布上限。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="load"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新状态
      </button>
    </header>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取认证状态"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="认证状态加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="load"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else-if="status">
      <BackofficeCard
        title="认证状态"
        description="状态以最近一次提交为准；一次只能有一份材料在审核中。"
      >
        <div
          class="qual-state"
          :class="stateTone"
          data-testid="qualification-state"
        >
          <span class="qual-state-label">{{ status.status_label }}</span>
          <span
            v-if="status.verified"
            class="qual-state-note"
          >学员端岗位会显示认证标识</span>
          <span
            v-else
            class="qual-state-note"
          >未认证企业最多发布 {{ status.limits.unverified_active_jobs }} 个在招岗位</span>
        </div>

        <dl
          v-if="status.record"
          class="qual-facts"
        >
          <div>
            <dt>企业名称</dt>
            <dd>{{ status.record.company_name }}</dd>
          </div>
          <div>
            <dt>统一社会信用代码</dt>
            <dd>{{ status.record.credit_code_masked }}</dd>
          </div>
          <div>
            <dt>提交时间</dt>
            <dd>{{ status.record.submitted_at }}</dd>
          </div>
          <div v-if="status.record.reviewed_at">
            <dt>审核时间</dt>
            <dd>{{ status.record.reviewed_at }}</dd>
          </div>
          <div v-if="status.record.expires_at">
            <dt>有效期至</dt>
            <dd>{{ status.record.expires_at }}</dd>
          </div>
        </dl>

        <p
          v-if="status.record?.status === 'rejected' && status.record.review_comment"
          class="qual-reject"
          role="alert"
        >
          <i
            class="fas fa-circle-exclamation"
            aria-hidden="true"
          />
          驳回原因：{{ status.record.review_comment }}
        </p>

        <p
          v-if="status.record && !status.record.has_license"
          class="qual-hint"
        >
          本条记录没有营业执照照片（演示数据），实际审核以证件照片为准。
        </p>

        <div
          v-if="status.record?.has_license"
          class="qual-license"
        >
          <button
            type="button"
            class="backoffice-button is-secondary"
            :disabled="licenseLoading"
            @click="previewLicense"
          >
            {{ licensePreview ? "收起证件照" : "查看营业执照" }}
          </button>
          <template v-if="licensePreview">
            <a
              v-if="licenseIsPdf"
              :href="licensePreview"
              target="_blank"
              rel="noopener noreferrer"
            >在新窗口打开 PDF</a>
            <img
              v-else
              :src="licensePreview"
              alt="营业执照"
            >
          </template>
        </div>
      </BackofficeCard>

      <BackofficeCard
        v-if="canSubmit"
        title="提交材料"
        description="统一社会信用代码会自动校验位，填错会当场提示。"
      >
        <form
          class="qual-form"
          @submit.prevent="submit"
        >
          <label for="qual-company">企业名称</label>
          <input
            id="qual-company"
            v-model="companyName"
            name="company_name"
            autocomplete="organization"
          >
          <label for="qual-credit">统一社会信用代码</label>
          <input
            id="qual-credit"
            v-model="creditCode"
            name="credit_code"
            maxlength="18"
            placeholder="18 位，与营业执照一致"
            autocomplete="off"
          >
          <label for="qual-legal">负责人姓名</label>
          <input
            id="qual-legal"
            v-model="legalPerson"
            name="legal_person"
            autocomplete="name"
          >
          <label for="qual-phone">联系电话</label>
          <input
            id="qual-phone"
            v-model="contactPhone"
            name="contact_phone"
            autocomplete="tel"
          >
          <label for="qual-address">注册地址</label>
          <input
            id="qual-address"
            v-model="address"
            name="address"
            autocomplete="street-address"
          >
          <label for="qual-industry">所属行业（选填）</label>
          <input
            id="qual-industry"
            v-model="industry"
            name="industry"
          >
          <label for="qual-size">企业规模（选填）</label>
          <input
            id="qual-size"
            v-model="companySize"
            name="company_size"
            placeholder="如 10-50 人"
          >
          <label for="qual-license">营业执照照片</label>
          <input
            id="qual-license"
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            @change="onFileChange"
          >
          <p class="qual-hint">
            支持 JPG / PNG / PDF，单张不超过 5MB。证件照保存在平台私有目录，仅审核人员可见。
          </p>

          <p
            v-if="submitError"
            class="qual-error"
            role="alert"
          >
            {{ submitError }}
          </p>
          <p
            v-if="submitMessage"
            class="qual-ok"
            role="status"
          >
            {{ submitMessage }}
          </p>

          <button
            type="submit"
            class="backoffice-button"
            :disabled="submitting"
          >
            {{ submitting ? "提交中…" : "提交审核" }}
          </button>
        </form>
      </BackofficeCard>

      <BackofficeCard
        v-else
        title="提交材料"
        description="当前状态不允许重复提交。"
      >
        <p class="qual-hint">
          {{ status.status === "pending"
            ? "材料已提交，正在等待审核。审核结果会在这里更新。"
            : "认证仍在有效期内。到期后可重新提交，届时会提前提示。" }}
        </p>
        <p
          v-if="status.status === 'pending'"
          class="qual-hint"
        >
          发现材料传错了可以直接撤回，撤回后可立即重新提交。
        </p>
        <button
          v-if="status.status === 'pending'"
          type="button"
          class="backoffice-button is-secondary qual-withdraw"
          :disabled="withdrawing"
          @click="withdraw"
        >
          {{ withdrawing ? "撤回中…" : "撤回申请" }}
        </button>
        <p
          v-if="submitError"
          class="qual-error"
          role="alert"
        >
          {{ submitError }}
        </p>
        <p
          v-if="submitMessage"
          class="qual-ok"
          role="status"
        >
          {{ submitMessage }}
        </p>
      </BackofficeCard>
    </template>
  </section>
</template>

<style scoped>
.qual-state {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--bo-accent);
  background: var(--surface-muted);
}

.qual-state.is-approved {
  border-left-color: var(--bo-success);
}

.qual-state.is-pending {
  border-left-color: var(--color-accent-gold);
}

.qual-state.is-rejected {
  border-left-color: var(--bo-danger);
}

.qual-state-label {
  font-weight: 600;
  color: var(--bo-text);
}

.qual-state-note {
  color: var(--bo-muted);
  font-size: 0.85rem;
}

.qual-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 24px;
  margin: 18px 0 0;
}

.qual-facts div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.qual-facts dt {
  font-size: 0.78rem;
  color: var(--bo-muted);
}

.qual-facts dd {
  margin: 0;
  color: var(--bo-text);
}

.qual-reject,
.qual-error {
  margin: 14px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  background: var(--state-error-bg);
  color: var(--bo-danger);
  font-size: 0.88rem;
}

.qual-ok {
  margin: 14px 0 0;
  color: var(--bo-success);
  font-size: 0.88rem;
}

.qual-hint {
  margin: 12px 0 0;
  color: var(--bo-muted);
  font-size: 0.82rem;
  line-height: 1.7;
}

.qual-withdraw {
  margin-top: 12px;
}

.qual-license {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  margin-top: 16px;
}

.qual-license img {
  max-width: 100%;
  max-height: 420px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-default);
}

.qual-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 6px 18px;
  align-items: start;
}

.qual-form label {
  margin-top: 10px;
  font-size: 0.82rem;
  color: var(--bo-muted);
}

.qual-form input {
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--bo-input-border);
  background: var(--bo-input-bg);
  color: var(--bo-text);
}

.qual-form .qual-hint,
.qual-form .qual-error,
.qual-form .qual-ok,
.qual-form button {
  grid-column: 1 / -1;
}

.qual-form button {
  margin-top: 16px;
  justify-self: start;
}
</style>
