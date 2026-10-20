<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import {
  createEnterpriseJob,
  deleteEnterpriseJob,
  getEnterpriseJobs,
  updateEnterpriseJob,
  type EnterpriseJob,
  type EnterpriseJobInput,
} from "@/api/enterprise";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

interface JobForm {
  title: string;
  salary: string;
  location: string;
  category: string;
  job_type: string;
  education: string;
  experience: string;
  industry: string;
  description: string;
  requirements: string;
}

const EMPTY_FORM: JobForm = {
  title: "",
  salary: "",
  location: "",
  category: "",
  job_type: "全职",
  education: "",
  experience: "",
  industry: "",
  description: "",
  requirements: "",
};

const jobs = ref<EnterpriseJob[]>([]);
const form = reactive<JobForm>({ ...EMPTY_FORM });
const editingId = ref<number | null>(null);
const loading = ref(true);
const saving = ref(false);
const deleting = ref(false);
const loadError = ref("");
const feedback = ref<{
  kind: "info" | "success" | "error";
  message: string;
} | null>(null);
const pendingDelete = ref<EnterpriseJob | null>(null);

const STATUS_LABELS: Record<string, string> = {
  approved: "已通过",
  pending: "待审核",
  rejected: "已驳回",
};

const STATUS_CLASSES: Record<string, string> = {
  approved: "is-approved",
  pending: "is-pending",
  rejected: "is-rejected",
};

async function loadJobs(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    jobs.value = await getEnterpriseJobs();
  } catch (requestError) {
    jobs.value = [];
    loadError.value =
      requestError instanceof Error ? requestError.message : "职位列表加载失败";
  } finally {
    loading.value = false;
  }
}

function resetForm(): void {
  Object.assign(form, EMPTY_FORM);
  editingId.value = null;
}

function startEdit(job: EnterpriseJob): void {
  editingId.value = job.id;
  form.title = job.title;
  form.salary = job.salary;
  form.location = job.location;
  form.category = job.category;
  form.job_type = job.job_type;
  form.education = job.education;
  form.experience = job.experience;
  form.industry = job.industry;
  form.description = job.description;
  form.requirements = job.requirements.join("\n");
  feedback.value = null;
}

function inputPayload(): EnterpriseJobInput {
  return {
    title: form.title.trim(),
    salary: form.salary.trim(),
    location: form.location.trim(),
    category: form.category.trim(),
    job_type: form.job_type.trim(),
    education: form.education.trim(),
    experience: form.experience.trim(),
    industry: form.industry.trim(),
    description: form.description.trim(),
    requirements: form.requirements
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
  };
}

async function saveJob(): Promise<void> {
  if (saving.value) return;
  const payload = inputPayload();
  if (!payload.title) {
    feedback.value = { kind: "error", message: "请输入职位标题" };
    return;
  }

  saving.value = true;
  feedback.value = null;
  try {
    const response =
      editingId.value === null
        ? await createEnterpriseJob(payload)
        : await updateEnterpriseJob(editingId.value, payload);
    feedback.value = {
      kind: response.success ? "success" : "error",
      message: response.message || "操作完成",
    };
    if (response.success) {
      resetForm();
      await loadJobs();
    }
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error ? requestError.message : "保存失败",
    };
  } finally {
    saving.value = false;
  }
}

function askDelete(job: EnterpriseJob): void {
  pendingDelete.value = job;
}

function cancelDelete(): void {
  if (!deleting.value) pendingDelete.value = null;
}

async function confirmDelete(): Promise<void> {
  const job = pendingDelete.value;
  if (!job || deleting.value) return;
  deleting.value = true;
  feedback.value = null;
  try {
    const response = await deleteEnterpriseJob(job.id);
    feedback.value = {
      kind: response.success ? "success" : "error",
      message: response.message || "删除完成",
    };
    if (response.success) {
      pendingDelete.value = null;
      if (editingId.value === job.id) resetForm();
      await loadJobs();
    }
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error ? requestError.message : "删除失败",
    };
  } finally {
    deleting.value = false;
  }
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status || "待审核";
}

function statusClass(status: string): string {
  return STATUS_CLASSES[status] || "is-pending";
}

onMounted(loadJobs);
</script>

<template>
  <section class="bo-page">
    <header class="bo-page-header">
      <div>
        <p>招聘管理</p>
        <h1>职位管理</h1>
        <span>发布、编辑与删除岗位，并跟踪平台审核结果。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
        :disabled="loading"
        @click="loadJobs"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新职位
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="enterprise-jobs-feedback"
    />

    <BackofficeCard
      :title="editingId === null ? '发布新职位' : '编辑职位'"
      :description="
        editingId === null
          ? '发布后进入待审核状态，审核通过后学员端才可见。'
          : '修改内容后会自动重新进入审核，避免绕过审核门禁。'
      "
    >
      <form
        class="enterprise-job-form"
        @submit.prevent="saveJob"
      >
        <div class="bo-form-grid">
          <label class="bo-field">
            <span>职位标题</span>
            <input
              v-model="form.title"
              required
              autocomplete="off"
              placeholder="如：农产品电商运营专员"
            >
          </label>
          <label class="bo-field">
            <span>薪资</span>
            <input
              v-model="form.salary"
              autocomplete="off"
              placeholder="如：5K-8K"
            >
          </label>
        </div>
        <div class="bo-form-grid">
          <label class="bo-field">
            <span>工作地点</span>
            <input
              v-model="form.location"
              autocomplete="off"
              placeholder="如：茂名"
            >
          </label>
          <label class="bo-field">
            <span>职位类别</span>
            <input
              v-model="form.category"
              autocomplete="off"
              placeholder="如：电商运营"
            >
          </label>
        </div>
        <div class="bo-form-grid">
          <label class="bo-field">
            <span>工作类型</span>
            <input
              v-model="form.job_type"
              autocomplete="off"
              placeholder="全职 / 兼职"
            >
          </label>
          <label class="bo-field">
            <span>学历要求</span>
            <input
              v-model="form.education"
              autocomplete="off"
              placeholder="如：大专 / 不限"
            >
          </label>
        </div>
        <div class="bo-form-grid">
          <label class="bo-field">
            <span>经验要求</span>
            <input
              v-model="form.experience"
              autocomplete="off"
              placeholder="如：1年 / 不限"
            >
          </label>
          <label class="bo-field">
            <span>所属行业</span>
            <input
              v-model="form.industry"
              autocomplete="off"
              placeholder="如：农业电商"
            >
          </label>
        </div>
        <label class="bo-field">
          <span>职位描述</span>
          <textarea
            v-model="form.description"
            rows="4"
            placeholder="描述岗位职责与工作内容"
          />
        </label>
        <label class="bo-field">
          <span>任职要求（每行一条）</span>
          <textarea
            v-model="form.requirements"
            rows="4"
            placeholder="熟悉直播运营&#10;会基础数据分析"
          />
        </label>
        <div class="bo-row-actions">
          <button
            type="submit"
            class="bo-button"
            :disabled="saving"
          >
            {{ saving ? "保存中..." : editingId === null ? "发布职位" : "保存并重新审核" }}
          </button>
          <button
            v-if="editingId !== null"
            type="button"
            class="bo-button is-secondary"
            :disabled="saving"
            @click="resetForm"
          >
            取消编辑
          </button>
        </div>
      </form>
    </BackofficeCard>

    <BackofficeCard
      title="我的职位"
      description="审核通过才会出现在学员端；驳回理由会随状态一起展示。"
      flush
    >
      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在加载职位"
      />
      <BackofficeState
        v-else-if="loadError"
        kind="error"
        title="职位列表加载失败"
        :detail="loadError"
      >
        <button
          type="button"
          class="bo-button"
          @click="loadJobs"
        >
          重试
        </button>
      </BackofficeState>
      <BackofficeState
        v-else-if="!jobs.length"
        kind="empty"
        title="暂无职位"
        detail="发布第一条职位后，审核状态会显示在这里。"
      />
      <div
        v-else
        class="bo-table-wrap"
      >
        <table class="bo-table">
          <thead>
            <tr>
              <th>职位</th>
              <th>薪资</th>
              <th>地点</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in jobs"
              :key="job.id"
              data-testid="enterprise-job-row"
              :data-job-id="job.id"
            >
              <td>
                <strong>{{ job.title }}</strong>
                <small>{{ job.category || "未分类" }} · {{ job.job_type || "全职" }}</small>
              </td>
              <td>{{ job.salary || "面议" }}</td>
              <td>{{ job.location || "广东" }}</td>
              <td>
                <span
                  class="review-pill"
                  :class="statusClass(job.review_status)"
                >
                  {{ statusLabel(job.review_status) }}
                </span>
                <small
                  v-if="job.review_status === 'rejected' && job.review_comment"
                  class="review-reason"
                >
                  驳回理由：{{ job.review_comment }}
                </small>
                <small v-else-if="job.reviewed_at">
                  审核时间：{{ job.reviewed_at }}
                </small>
              </td>
              <td>
                <div class="bo-row-actions">
                  <button
                    type="button"
                    class="bo-button is-small is-secondary"
                    @click="startEdit(job)"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    class="bo-button is-small is-danger"
                    @click="askDelete(job)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </BackofficeCard>

    <Teleport to="body">
      <div
        v-if="pendingDelete"
        class="bo-modal-overlay"
        @click.self="cancelDelete"
      >
        <div
          class="bo-modal is-confirm"
          data-testid="enterprise-job-delete-confirm"
          role="dialog"
          aria-modal="true"
          aria-label="确认删除职位"
        >
          <header class="bo-modal-head">
            <div>
              <p>删除确认</p>
              <h2>确认删除职位</h2>
            </div>
          </header>
          <div class="bo-modal-body">
            <p class="bo-confirm-copy">
              确定删除「{{ pendingDelete.title }}」？该职位及其收藏记录会被移除，此操作不可恢复。
            </p>
          </div>
          <footer class="bo-modal-actions">
            <button
              type="button"
              class="bo-button is-secondary"
              :disabled="deleting"
              @click="cancelDelete"
            >
              取消
            </button>
            <button
              type="button"
              class="bo-button is-danger"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? "删除中..." : "确认删除" }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.enterprise-job-form {
  display: grid;
  gap: 14px;
}

.bo-field textarea {
  width: 100%;
  min-height: 90px;
  padding: 9px 10px;
  border: 1px solid var(--bo-input-border);
  border-radius: 8px;
  background: var(--bo-input-bg);
  color: var(--bo-text);
  font: inherit;
  font-size: 0.84rem;
  line-height: 1.6;
  resize: vertical;
}

.bo-field textarea:focus {
  border-color: var(--bo-accent);
  box-shadow: 0 0 0 3px var(--bo-accent-soft);
  outline: none;
}

.review-pill {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  white-space: nowrap;
}

.review-pill.is-approved {
  background: rgba(31, 107, 66, 0.12);
  color: var(--bo-success);
}

.review-pill.is-pending {
  background: rgba(186, 117, 23, 0.13);
  color: #9a6413;
}

.review-pill.is-rejected {
  background: rgba(179, 56, 47, 0.12);
  color: var(--bo-danger);
}

.review-reason {
  max-width: 260px;
  color: var(--bo-danger);
  line-height: 1.45;
}

[data-theme="dark"] .review-pill.is-pending {
  color: #efc75e;
}
</style>
