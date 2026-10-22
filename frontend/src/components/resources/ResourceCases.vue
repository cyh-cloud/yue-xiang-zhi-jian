<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import {
  getCases,
  type CasesResponse,
  type SuccessCase,
} from "@/api/resources";

const data = ref<CasesResponse | null>(null);
const loading = ref(true);
const error = ref("");

onMounted(() => {
  void loadCases();
});

async function loadCases(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    data.value = await getCases();
  } catch {
    data.value = null;
    error.value = "案例加载失败，请检查网络后重试";
  } finally {
    loading.value = false;
  }
}

function statChips(item: SuccessCase) {
  return item.stats.slice(0, 2);
}
</script>

<template>
  <section
    class="card-section"
    aria-labelledby="cases-title"
  >
    <h2
      id="cases-title"
      class="card-section-title"
    >
      <i
        class="fas fa-trophy"
        aria-hidden="true"
      />
      本地成功案例
    </h2>
    <div class="cases-grid">
      <div
        v-if="loading"
        class="cases-placeholder"
        role="status"
      >
        <i
          class="fas fa-spinner fa-spin"
          aria-hidden="true"
        />
        正在加载案例…
      </div>
      <div
        v-else-if="error"
        class="cases-error"
        role="alert"
      >
        <i
          class="fas fa-exclamation-circle"
          aria-hidden="true"
        />
        <p>{{ error }}</p>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="loadCases"
        >
          <i
            class="fas fa-redo"
            aria-hidden="true"
          />
          重试
        </button>
      </div>
      <div
        v-else-if="data && data.cases.length === 0 && data.case_review.pending > 0"
        class="cases-pending"
        role="status"
      >
        <i
          class="fas fa-user-shield"
          aria-hidden="true"
        />
        <p>案例内容正在审核中（{{ data.case_review.pending }} 条待审）</p>
        <span>本地成功案例需经超级管理员审核通过后展示</span>
      </div>
      <div
        v-else-if="data && data.cases.length === 0"
        class="cases-error"
        role="status"
      >
        <i
          class="fas fa-folder-open"
          aria-hidden="true"
        />
        <p>暂无案例数据</p>
      </div>
      <template v-else>
        <article
          v-for="item in data?.cases ?? []"
          :key="item.id"
          class="case-card"
          data-testid="case-card"
          :data-case-id="item.id"
        >
          <div class="case-visual">
            <i
              class="fas fa-map-marker-alt"
              aria-hidden="true"
            />
          </div>
          <div class="case-body">
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
            <div class="case-stats">
              <span
                v-for="stat in statChips(item)"
                :key="`${stat.label}-${stat.value}`"
              >
                <i
                  class="fas"
                  :class="stat.icon || 'fa-chart-line'"
                  aria-hidden="true"
                />
                {{ stat.label }}：{{ stat.value }}
              </span>
            </div>
            <RouterLink
              class="btn btn-outline btn-sm"
              :to="`/case-detail/${item.id}`"
            >
              查看详情
              <i
                class="fas fa-arrow-right"
                aria-hidden="true"
              />
            </RouterLink>
          </div>
        </article>
      </template>
    </div>
  </section>
</template>

<style scoped>
.case-body h3 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 600;
}

.case-card {
  display: flex;
  flex-direction: column;
}

.case-body {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.case-body .btn {
  align-self: flex-start;
}
</style>
