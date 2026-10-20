<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import {
  getOperatorFarmingCategories,
  getOperatorFarmingProducts,
  getOperatorFarmingSources,
  getOperatorFarmingTasks,
  getOperatorPestCrops,
  getOperatorPestEntries,
  getOperatorPestSources,
  getOperatorPhenophases,
  type OperatorFarmingTask,
  type OperatorPestEntrySummary,
} from "@/api/operator";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

interface Inventory {
  products: number;
  phenophases: number;
  farmingSources: number;
  categories: number;
  pestCrops: number;
  pestSources: number;
}

const loading = ref(true);
const error = ref("");
const tasks = ref<OperatorFarmingTask[]>([]);
const overdueTasks = ref<OperatorFarmingTask[]>([]);
const entries = ref<OperatorPestEntrySummary[]>([]);
const overdueEntries = ref<OperatorPestEntrySummary[]>([]);
const inventory = ref<Inventory>({
  products: 0,
  phenophases: 0,
  farmingSources: 0,
  categories: 0,
  pestCrops: 0,
  pestSources: 0,
});

const totalOverdue = computed(
  () => overdueTasks.value.length + overdueEntries.value.length,
);
const inventorySummary = computed(
  () =>
    `${inventory.value.products} 个作物 · ${inventory.value.phenophases} 个物候期 · ` +
    `${inventory.value.farmingSources} 条农时来源 · ${inventory.value.categories} 个分类`,
);
const pestInventorySummary = computed(
  () =>
    `${inventory.value.pestCrops} 个速查作物 · ${inventory.value.pestSources} 条病虫来源`,
);

async function loadOverview(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [
      nextTasks,
      nextOverdueTasks,
      nextEntries,
      nextOverdueEntries,
      products,
      phenophases,
      farmingSources,
      categories,
      pestCrops,
      pestSources,
    ] = await Promise.all([
      getOperatorFarmingTasks(),
      getOperatorFarmingTasks({ overdue: true }),
      getOperatorPestEntries(),
      getOperatorPestEntries({ overdue: true }),
      getOperatorFarmingProducts(),
      getOperatorPhenophases(),
      getOperatorFarmingSources(),
      getOperatorFarmingCategories(),
      getOperatorPestCrops(),
      getOperatorPestSources(),
    ]);
    tasks.value = nextTasks;
    overdueTasks.value = nextOverdueTasks;
    entries.value = nextEntries;
    overdueEntries.value = nextOverdueEntries;
    inventory.value = {
      products: products.length,
      phenophases: phenophases.length,
      farmingSources: farmingSources.length,
      categories: categories.length,
      pestCrops: pestCrops.length,
      pestSources: pestSources.length,
    };
  } catch (failure) {
    tasks.value = [];
    overdueTasks.value = [];
    entries.value = [];
    overdueEntries.value = [];
    error.value =
      failure instanceof Error ? failure.message : "运营总览加载失败";
  } finally {
    loading.value = false;
  }
}

function verificationText(
  item: OperatorFarmingTask | OperatorPestEntrySummary,
): string {
  return item.is_verified
    ? `${item.verified_by || "已复核"} ${item.verified_at || ""}`.trim()
    : "从未复核";
}

onMounted(loadOverview);
</script>

<template>
  <section
    class="bo-page operator-overview"
    data-testid="operator-overview"
  >
    <header class="bo-page-header">
      <div>
        <p>内容运营</p>
        <h1 data-testid="backoffice-page-title">
          运营工作台
        </h1>
        <span>农时与病虫害内容的真实存量、复核状态和待办提醒。</span>
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
      title="正在读取运营统计"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="运营总览加载失败"
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

    <template v-else>
      <BackofficeCard
        title="内容与待复核"
        description="超 183 天未重新复核的内容会和从未复核内容一起进入待办。"
      >
        <div class="bo-stat-grid">
          <article
            class="bo-stat-card"
            data-testid="operator-stat-tasks"
          >
            <strong>{{ tasks.length }}</strong>
            <span>农事任务</span>
            <small>{{ inventorySummary }}</small>
          </article>
          <article
            class="bo-stat-card is-alert"
            data-testid="operator-stat-overdue-tasks"
          >
            <strong>{{ overdueTasks.length }}</strong>
            <span>待重新复核的农事任务</span>
            <small>超 183 天或从未复核</small>
          </article>
          <article
            class="bo-stat-card"
            data-testid="operator-stat-entries"
          >
            <strong>{{ entries.length }}</strong>
            <span>病虫害条目</span>
            <small>{{ pestInventorySummary }}</small>
          </article>
          <article
            class="bo-stat-card is-alert"
            data-testid="operator-stat-overdue-entries"
          >
            <strong>{{ overdueEntries.length }}</strong>
            <span>待重新复核的病虫害条目</span>
            <small>超 183 天或从未复核</small>
          </article>
        </div>
      </BackofficeCard>

      <BackofficeCard
        title="待复核提醒"
        :description="`共 ${totalOverdue} 项需要重新确认。复核结论会过期，过期内容在公开页按推算参考展示。`"
        data-testid="operator-overdue-reminders"
      >
        <p class="operator-overdue-criterion">
          筛选口径：超 183 天或从未复核。公开页会把过期复核降级为推算参考。
        </p>
        <div
          v-if="!totalOverdue"
          class="operator-overview-empty"
        >
          <i
            class="fas fa-circle-check"
            aria-hidden="true"
          />
          当前没有超过 183 天或从未复核的内容。
        </div>

        <div
          v-else
          class="operator-overdue-columns"
        >
          <section>
            <header>
              <h3>农事任务</h3>
              <RouterLink to="/operator/farming">
                去维护
              </RouterLink>
            </header>
            <ul v-if="overdueTasks.length">
              <li
                v-for="task in overdueTasks.slice(0, 8)"
                :key="task.id"
              >
                <strong>{{ task.title }}</strong>
                <span>{{ task.product_name || task.product_id }} · {{ task.month }} 月</span>
                <small>{{ verificationText(task) }}</small>
              </li>
            </ul>
            <p v-else>
              没有待复核的农事任务。
            </p>
          </section>

          <section>
            <header>
              <h3>病虫害条目</h3>
              <RouterLink to="/operator/pest">
                去维护
              </RouterLink>
            </header>
            <ul v-if="overdueEntries.length">
              <li
                v-for="entry in overdueEntries.slice(0, 8)"
                :key="entry.id"
              >
                <strong>{{ entry.disease }}</strong>
                <span>{{ entry.crop_name }} · {{ entry.kind === "pest" ? "虫害" : "病害" }}</span>
                <small>{{ verificationText(entry) }}</small>
              </li>
            </ul>
            <p v-else>
              没有待复核的病虫害条目。
            </p>
          </section>
        </div>
      </BackofficeCard>

      <p class="bo-note">
        口径说明：只统计当前数据库真实存在的农时与病虫害内容。运营负责内容维护与复核，
        用户管理和发布前审核属于超级管理员职责，本工作台不提供这两个入口。
      </p>
    </template>
  </section>
</template>

<style scoped>
.operator-overdue-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.operator-overdue-criterion {
  margin: -4px 0 14px;
  padding: 9px 11px;
  border-radius: 8px;
  background: var(--bo-accent-soft);
  color: var(--bo-muted);
  font-size: 0.74rem;
  line-height: 1.55;
}

.operator-overdue-columns section {
  padding: 15px;
  border: 1px solid var(--bo-card-border);
  border-radius: 11px;
  background: color-mix(in srgb, var(--bo-card-bg) 92%, var(--bo-page-bg));
}

.operator-overdue-columns header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.operator-overdue-columns h3,
.operator-overdue-columns p {
  margin: 0;
}

.operator-overdue-columns h3 {
  font-size: 0.86rem;
}

.operator-overdue-columns a {
  color: var(--bo-accent);
  font-size: 0.74rem;
  font-weight: 700;
}

.operator-overdue-columns ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.operator-overdue-columns li {
  display: grid;
  gap: 2px;
  padding: 9px 10px;
  border-radius: 8px;
  background: var(--bo-accent-soft);
}

.operator-overdue-columns li strong {
  font-size: 0.78rem;
}

.operator-overdue-columns li span,
.operator-overdue-columns li small,
.operator-overdue-columns p {
  color: var(--bo-muted);
  font-size: 0.7rem;
  line-height: 1.45;
}

.operator-overview-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--bo-muted);
  font-size: 0.82rem;
}

@media (max-width: 900px) {
  .operator-overdue-columns {
    grid-template-columns: 1fr;
  }
}
</style>
