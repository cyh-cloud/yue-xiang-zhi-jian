<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  getGovernmentOverview,
  type GovernmentOverview,
} from "@/api/government";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const overview = ref<GovernmentOverview | null>(null);
const loading = ref(true);
const error = ref("");

const categorySummary = computed(() => {
  const categories = overview.value?.policies.categories ?? [];
  if (!categories.length) return "暂无政策";
  return categories
    .map((item) => `${item.category} ${item.count}`)
    .join(" · ");
});

const regionSummary = computed(() => {
  const regions = overview.value?.cases.regions ?? [];
  if (!regions.length) return "暂无已通过审核的案例";
  return regions.map((item) => `${item.region} ${item.count}`).join(" · ");
});

async function loadOverview(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    overview.value = await getGovernmentOverview();
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
  <section
    class="bo-page"
    data-testid="government-dashboard"
  >
    <header class="bo-page-header">
      <div>
        <p>政务工作</p>
        <h1 data-testid="backoffice-page-title">
          政府工作台
        </h1>
        <span>只呈现政务侧产生、可核对的政策与本地案例信息。</span>
      </div>
      <button
        type="button"
        class="bo-button is-secondary"
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
      title="正在读取政务概览"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="政务概览加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="bo-button"
        @click="loadOverview"
      >
        重试
      </button>
    </BackofficeState>

    <template v-else-if="overview">
      <BackofficeCard
        title="政策发布情况"
        description="区分本级发布与平台预置，避免把平台整理内容计入本级政绩。"
      >
        <div class="bo-stat-grid">
          <article
            class="bo-stat-card is-alert"
            data-testid="government-own-total"
          >
            <strong>{{ overview.policies.own.total }}</strong>
            <span>本级发布政策</span>
            <small data-testid="government-own-published">
              已上线 {{ overview.policies.own.published }}
            </small>
            <small data-testid="government-own-unpublished">
              已下架 {{ overview.policies.own.unpublished }}
            </small>
          </article>
          <article
            class="bo-stat-card"
            data-testid="government-preset-total"
          >
            <strong>{{ overview.policies.preset.total }}</strong>
            <span>平台预置参考</span>
            <small>
              已上线 {{ overview.policies.preset.published }} · 已下架
              {{ overview.policies.preset.unpublished }}
            </small>
          </article>
          <article
            class="bo-stat-card"
            data-testid="government-category-count"
          >
            <strong>{{ overview.policies.categories.length }}</strong>
            <span>政策分类</span>
            <small>{{ categorySummary }}</small>
          </article>
        </div>
      </BackofficeCard>

      <BackofficeCard
        title="本地成功案例"
        description="只统计已通过审核的案例，与学员端可见口径一致。"
      >
        <div class="bo-stat-grid">
          <article
            class="bo-stat-card"
            data-testid="government-approved-cases"
          >
            <strong>{{ overview.cases.approved }}</strong>
            <span>已收录案例</span>
            <small>
              共 {{ overview.cases.total }} 条，其余审核中或未通过
            </small>
          </article>
          <article class="bo-stat-card">
            <strong>{{ overview.cases.regions.length }}</strong>
            <span>覆盖地市</span>
            <small>{{ regionSummary }}</small>
          </article>
          <article class="bo-stat-card">
            <strong>{{ overview.cases.avg_sources }}</strong>
            <span>平均来源数</span>
            <small>合计 {{ overview.cases.source_total }} 条公开出处</small>
          </article>
        </div>

        <div
          v-if="overview.cases.items.length"
          class="government-case-chips"
        >
          <span
            v-for="item in overview.cases.items"
            :key="item.id"
          >
            {{ item.region ? `${item.region} · ` : "" }}{{ item.title }}
            （{{ item.sources }} 条来源）
          </span>
        </div>
        <BackofficeState
          v-else
          kind="empty"
          title="暂无已通过审核的本地案例"
        />
      </BackofficeCard>

      <p
        class="bo-note"
        data-testid="government-dashboard-note"
      >
        口径说明：本页只呈现政务侧产生的信息，即政策发布情况与本地成功案例；
        岗位数请在企业端工作台查看。政策与案例均依据公开文件或公开报道整理，
        具体标准与办理时限以当年度当地主管部门正式文件为准。
      </p>
    </template>
  </section>
</template>

<style scoped>
.government-case-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.government-case-chips span {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--bo-accent-soft);
  color: var(--bo-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}
</style>
