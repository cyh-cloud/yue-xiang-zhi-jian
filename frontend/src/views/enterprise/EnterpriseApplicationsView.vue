<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  getEnterpriseApplications,
  updateEnterpriseApplicationStatus,
  type EnterpriseApplication,
} from "@/api/enterprise";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const applications = ref<EnterpriseApplication[]>([]);
const expandedIds = ref<Set<number>>(new Set());
const busyId = ref<number | null>(null);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{
  kind: "info" | "success" | "error";
  message: string;
} | null>(null);

const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  interview: "已通知面试",
  approved: "已通过",
  rejected: "已拒绝",
};

const STATUS_CLASSES: Record<string, string> = {
  pending: "is-pending",
  interview: "is-interview",
  approved: "is-approved",
  rejected: "is-rejected",
};

const statusCounts = computed(() => {
  const counts = {
    pending: 0,
    interview: 0,
    approved: 0,
    rejected: 0,
  };
  for (const application of applications.value) {
    if (application.status in counts) {
      counts[application.status as keyof typeof counts] += 1;
    }
  }
  return counts;
});

async function loadApplications(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    applications.value = await getEnterpriseApplications();
  } catch (requestError) {
    applications.value = [];
    loadError.value =
      requestError instanceof Error ? requestError.message : "投递列表加载失败";
  } finally {
    loading.value = false;
  }
}

function toggleResume(applicationId: number): void {
  const next = new Set(expandedIds.value);
  if (next.has(applicationId)) next.delete(applicationId);
  else next.add(applicationId);
  expandedIds.value = next;
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status || "待处理";
}

function statusClass(status: string): string {
  return STATUS_CLASSES[status] || "is-pending";
}

function contactPhone(application: EnterpriseApplication): string {
  return application.resume_phone || application.applicant_phone || "";
}

function hasResumeContent(application: EnterpriseApplication): boolean {
  return Boolean(
    application.resume_title ||
      application.resume_region ||
      application.resume_education ||
      application.resume_work_years ||
      application.resume_phone ||
      application.resume_email ||
      application.resume_self_eval ||
      application.resume_skills ||
      experienceLines(application.resume_experience).length,
  );
}

function experienceLines(raw: string | null): string[] {
  if (!raw?.trim() || raw.trim() === "[]" || raw.trim() === "{}") return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [raw];
    return parsed
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return "";
        const record = item as Record<string, unknown>;
        const heading = [record.company, record.position, record.period]
          .filter((value) => typeof value === "string" && value)
          .join(" / ");
        const desc = typeof record.desc === "string" ? record.desc : "";
        return [heading, desc].filter(Boolean).join("：");
      })
      .filter(Boolean);
  } catch {
    return [raw];
  }
}

async function changeStatus(
  application: EnterpriseApplication,
  status: "interview" | "approved" | "rejected",
): Promise<void> {
  if (busyId.value !== null) return;
  busyId.value = application.id;
  feedback.value = null;
  try {
    const response = await updateEnterpriseApplicationStatus(
      application.id,
      status,
    );
    feedback.value = {
      kind: response.success ? "success" : "error",
      message: response.message || "操作完成",
    };
    if (response.success) await loadApplications();
  } catch (requestError) {
    feedback.value = {
      kind: "error",
      message:
        requestError instanceof Error ? requestError.message : "状态更新失败",
    };
  } finally {
    busyId.value = null;
  }
}

onMounted(loadApplications);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>招聘管理</p>
        <h1>简历管理</h1>
        <span>查看投递学员的简历，并更新招聘处理状态。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadApplications"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新投递
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="enterprise-applications-feedback"
    />

    <BackofficeCard
      title="投递处理"
      description="状态变化会同步到学员的共享消息中心投递来源。"
      flush
    >
      <div class="status-summary">
        <span>待处理 {{ statusCounts.pending }}</span>
        <span>已通知面试 {{ statusCounts.interview }}</span>
        <span>已通过 {{ statusCounts.approved }}</span>
        <span>已拒绝 {{ statusCounts.rejected }}</span>
      </div>

      <BackofficeState
        v-if="loading"
        kind="loading"
        title="正在加载投递"
      />
      <BackofficeState
        v-else-if="loadError"
        kind="error"
        title="投递列表加载失败"
        :detail="loadError"
      >
        <button
          type="button"
          class="backoffice-button"
          @click="loadApplications"
        >
          重试
        </button>
      </BackofficeState>
      <BackofficeState
        v-else-if="!applications.length"
        kind="empty"
        title="暂无简历投递"
        detail="学员投递本企业已通过审核的岗位后，简历会显示在这里。"
      />
      <div
        v-else
        class="backoffice-table-wrap"
      >
        <table class="backoffice-table">
          <thead>
            <tr>
              <th>申请人</th>
              <th>职位</th>
              <th>联系方式</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="application in applications"
              :key="application.id"
            >
              <tr
                data-testid="enterprise-application-row"
                :data-application-id="application.id"
              >
                <td>
                  <strong>{{ application.applicant_name || application.user_id }}</strong>
                  <small>{{ application.applied_at }}</small>
                </td>
                <td>{{ application.job_title }}</td>
                <td>{{ contactPhone(application) || "未填写" }}</td>
                <td>
                  <span
                    class="application-pill"
                    :class="statusClass(application.status)"
                  >
                    {{ statusLabel(application.status) }}
                  </span>
                </td>
                <td>
                  <div class="backoffice-row-actions">
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      @click="toggleResume(application.id)"
                    >
                      {{ expandedIds.has(application.id) ? "收起简历" : "查看简历" }}
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-secondary"
                      :disabled="busyId !== null || application.status === 'interview'"
                      @click="changeStatus(application, 'interview')"
                    >
                      通知面试
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-success"
                      :disabled="busyId !== null || application.status === 'approved'"
                      @click="changeStatus(application, 'approved')"
                    >
                      通过
                    </button>
                    <button
                      type="button"
                      class="backoffice-button is-small is-danger"
                      :disabled="busyId !== null || application.status === 'rejected'"
                      @click="changeStatus(application, 'rejected')"
                    >
                      拒绝
                    </button>
                  </div>
                </td>
              </tr>
              <tr
                v-if="expandedIds.has(application.id)"
                class="resume-row"
                data-testid="enterprise-resume-detail"
              >
                <td colspan="5">
                  <div
                    v-if="hasResumeContent(application)"
                    class="resume-detail"
                  >
                    <div class="resume-grid">
                      <span v-if="application.resume_title">
                        意向岗位：{{ application.resume_title }}
                      </span>
                      <span v-if="application.resume_region">
                        期望地区：{{ application.resume_region }}
                      </span>
                      <span v-if="application.resume_education">
                        学历：{{ application.resume_education }}
                      </span>
                      <span v-if="application.resume_work_years">
                        工作年限：{{ application.resume_work_years }}
                      </span>
                      <span v-if="application.resume_phone">
                        联系电话：{{ application.resume_phone }}
                      </span>
                      <span v-if="application.resume_email">
                        邮箱：{{ application.resume_email }}
                      </span>
                    </div>
                    <div
                      v-if="application.resume_self_eval"
                      class="resume-block"
                    >
                      <h3>自我评价</h3>
                      <p>{{ application.resume_self_eval }}</p>
                    </div>
                    <div
                      v-if="application.resume_skills"
                      class="resume-block"
                    >
                      <h3>技能</h3>
                      <p>{{ application.resume_skills }}</p>
                    </div>
                    <div
                      v-if="experienceLines(application.resume_experience).length"
                      class="resume-block"
                    >
                      <h3>经历</h3>
                      <p
                        v-for="line in experienceLines(application.resume_experience)"
                        :key="line"
                      >
                        {{ line }}
                      </p>
                    </div>
                    <small v-if="application.resume_updated_at">
                      简历更新时间：{{ application.resume_updated_at }}
                    </small>
                  </div>
                  <p
                    v-else
                    class="resume-empty"
                  >
                    该学员尚未填写简历内容，平台不会代为补写。
                  </p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </BackofficeCard>
  </section>
</template>

<style src="./enterprise.css"></style>
