<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  getEnterpriseApplications,
  getEnterpriseStats,
  type EnterpriseApplication,
  type EnterpriseStats,
} from "@/api/enterprise";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const stats = ref<EnterpriseStats | null>(null);
const applications = ref<EnterpriseApplication[]>([]);
const loading = ref(true);
const error = ref("");

const cards = computed(() => {
  if (!stats.value) return [];
  return [
    {
      testid: "enterprise-stat-approved",
      label: "在招职位",
      value: stats.value.total_jobs,
      detail: "已通过审核，学员端可见",
    },
    {
      testid: "enterprise-stat-pending",
      label: "待审核岗位",
      value: stats.value.pending_jobs,
      detail: stats.value.pending_jobs
        ? "待审核或已驳回，学员端不可见"
        : "暂无待审核岗位",
    },
    {
      testid: "enterprise-stat-applications",
      label: "收到简历",
      value: stats.value.total_applications,
      detail: "来自本企业岗位的真实投递",
    },
  ];
});

const applicationStatusCards = computed(() => {
  const counts: Record<string, number> = {
    pending: 0,
    interview: 0,
    approved: 0,
    rejected: 0,
  };
  for (const application of applications.value) {
    if (application.status in counts) {
      counts[application.status] = (counts[application.status] ?? 0) + 1;
    }
  }
  return [
    {
      status: "pending",
      label: "待处理",
      value: counts.pending,
      detail: "企业尚未处理",
    },
    {
      status: "interview",
      label: "已通知面试",
      value: counts.interview,
      detail: "已进入面试环节",
    },
    {
      status: "approved",
      label: "已通过",
      value: counts.approved,
      detail: "招聘流程通过",
    },
    {
      status: "rejected",
      label: "已拒绝",
      value: counts.rejected,
      detail: "招聘流程未通过",
    },
  ];
});

async function loadStats(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [nextStats, nextApplications] = await Promise.all([
      getEnterpriseStats(),
      getEnterpriseApplications(),
    ]);
    stats.value = nextStats;
    applications.value = nextApplications;
  } catch (requestError) {
    stats.value = null;
    applications.value = [];
    error.value =
      requestError instanceof Error ? requestError.message : "统计加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadStats);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>招聘管理</p>
        <h1>企业中心</h1>
        <span>岗位发布、审核状态与投递处理集中在同一工作台。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadStats"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新统计
      </button>
    </header>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在读取招聘统计"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="统计加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadStats"
      >
        重试
      </button>
    </BackofficeState>

    <BackofficeCard
      v-else
      title="招聘概览"
      description="只统计当前企业账号真实发布的岗位与收到的投递。"
    >
      <div class="backoffice-stat-grid">
        <article
          v-for="card in cards"
          :key="card.testid"
          class="backoffice-stat-card"
          :data-testid="card.testid"
        >
          <strong>{{ card.value }}</strong>
          <span>{{ card.label }}</span>
          <small>{{ card.detail }}</small>
        </article>
      </div>
    </BackofficeCard>

    <BackofficeCard
      v-if="!loading && !error && stats"
      title="投递状态"
      description="按企业当前收到的投递记录统计，状态与简历管理页一致。"
    >
      <div class="backoffice-stat-grid">
        <article
          v-for="card in applicationStatusCards"
          :key="card.status"
          class="backoffice-stat-card"
          :data-testid="`enterprise-application-status-${card.status}`"
        >
          <strong>{{ card.value }}</strong>
          <span>{{ card.label }}</span>
          <small>{{ card.detail }}</small>
        </article>
      </div>
    </BackofficeCard>
  </section>
</template>

<style src="./enterprise.css"></style>
