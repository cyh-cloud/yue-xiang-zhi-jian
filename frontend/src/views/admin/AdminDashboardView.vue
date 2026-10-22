<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { getAdminOverview, type AdminOverview } from "@/api/admin";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

interface StatCard {
  label: string;
  value: number;
  detail: string;
  testid?: string;
}

const overview = ref<AdminOverview | null>(null);
const loading = ref(true);
const error = ref("");

const pendingCards = computed<StatCard[]>(() => {
  if (!overview.value) return [];
  const data = overview.value;
  const cards: StatCard[] = [
    {
      label: "待审核内容",
      value: data.reviews.pending,
      detail:
        data.reviews.oldest_pending_days === null
          ? "暂无等待时长数据"
          : data.reviews.oldest_pending_days === 0
            ? "最久已等待不到 1 天"
            : `最久已等待 ${data.reviews.oldest_pending_days} 天`,
    },
    {
      label: "停用账号",
      value: data.users.suspended,
      detail: `共 ${data.users.total} 个账号`,
    },
  ];
  return cards;
});

const inventoryCards = computed<StatCard[]>(() => {
  if (!overview.value) return [];
  const { users, content } = overview.value;
  const cards: StatCard[] = [
    {
      label: "账号总数",
      value: users.total,
      detail: "库内真实账号",
      testid: "admin-stat-users-total",
    },
  ];
  if (typeof users.student === "number") {
    cards.push({
      label: "学员账号",
      value: users.student,
      detail: "学习与就业服务对象",
    });
  }
  const organizationCount = [
    users.teacher,
    users.enterprise,
    users.government,
    users.operator,
  ].filter((value): value is number => typeof value === "number");
  if (organizationCount.length === 4) {
    cards.push({
      label: "教师 / 企业 / 政府 / 运营",
      value: organizationCount.reduce((sum, value) => sum + value, 0),
      detail: "平台服务与管理角色",
    });
  }
  const contentCount = [
    content.jobs,
    content.models,
    content.cases,
    content.policies,
  ].filter((value): value is number => typeof value === "number");
  if (contentCount.length === 4) {
    cards.push({
      label: "岗位 / 模型 / 案例 / 政策",
      value: contentCount.reduce((sum, value) => sum + value, 0),
      detail: "平台内容存量",
    });
  }
  return cards;
});

async function loadOverview(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    overview.value = await getAdminOverview();
  } catch (requestError) {
    overview.value = null;
    error.value =
      requestError instanceof Error ? requestError.message : "统计加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>平台治理</p>
        <h1 data-testid="backoffice-page-title">
          系统管理后台
        </h1>
        <span>账号、审核与内容治理的真实运行概览。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadOverview"
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
      title="正在读取平台统计"
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
        @click="loadOverview"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else-if="overview">
      <BackofficeCard
        title="待处理"
        description="需要管理员尽快采取行动的账号与审核事项。"
      >
        <div class="backoffice-stat-grid">
          <article
            v-for="card in pendingCards"
            :key="card.label"
            class="backoffice-stat-card is-alert"
          >
            <strong>{{ card.value }}</strong>
            <span>{{ card.label }}</span>
            <small>{{ card.detail }}</small>
          </article>
        </div>
      </BackofficeCard>

      <BackofficeCard
        title="账号与内容存量"
        description="仅展示当前数据库能够真实计算的指标。"
      >
        <div class="backoffice-stat-grid">
          <article
            v-for="card in inventoryCards"
            :key="card.label"
            class="backoffice-stat-card"
            :data-testid="card.testid"
          >
            <strong>{{ card.value }}</strong>
            <span>{{ card.label }}</span>
            <small>{{ card.detail }}</small>
          </article>
        </div>
        <p
          class="backoffice-note"
          data-testid="admin-dashboard-note"
        >
          口径说明：仅统计库内真实可算的项；在线人数、日活、增长趋势与平均审核时长因缺少数据源，不予展示。
        </p>
      </BackofficeCard>
    </template>
  </section>
</template>

<style src="./admin.css"></style>
