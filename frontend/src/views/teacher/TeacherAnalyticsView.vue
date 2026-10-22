<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  getTeacherAnalytics,
  type TeacherAnalytics,
} from "@/api/teacher";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const analytics = ref<TeacherAnalytics | null>(null);
const loading = ref(true);
const error = ref("");

const maxProgressCount = computed(() =>
  Math.max(
    1,
    ...(analytics.value?.progress_distribution.map((item) => item.count) ?? []),
  ),
);

const directionTotal = computed(() =>
  Math.max(
    1,
    (analytics.value?.direction_distribution ?? []).reduce(
      (total, item) => total + item.count,
      0,
    ),
  ),
);

function errorMessage(value: unknown): string {
  if (value instanceof ApiError || value instanceof Error) {
    return value.message || "学情数据加载失败";
  }
  return "学情数据加载失败";
}

async function loadAnalytics(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    analytics.value = await getTeacherAnalytics();
  } catch (requestError) {
    analytics.value = null;
    error.value = errorMessage(requestError);
  } finally {
    loading.value = false;
  }
}

function progressWidth(count: number): string {
  return `${Math.min(100, (count / maxProgressCount.value) * 100).toFixed(1)}%`;
}

function directionWidth(count: number): string {
  return `${Math.min(100, (count / directionTotal.value) * 100).toFixed(1)}%`;
}

onMounted(loadAnalytics);
</script>

<template>
  <section
    class="backoffice-page"
    data-testid="teacher-analytics"
  >
    <header class="backoffice-page-header">
      <div>
        <p>教学工作</p>
        <h1>学情分析</h1>
        <span>完成度口径为学员名下证书进度的平均值，不读取名册手填进度。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadAnalytics"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在加载学情数据"
    />
    <BackofficeState
      v-else-if="error"
      kind="error"
      title="学情数据加载失败"
      :detail="error"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadAnalytics"
      >
        重试
      </button>
    </BackofficeState>
    <BackofficeState
      v-else-if="!analytics || analytics.roster_count === 0"
      kind="empty"
      title="暂无学员数据"
      detail="添加学员并产生证书记录后，这里会展示进度与方向分布。"
      data-testid="teacher-analytics-empty"
    />
    <template v-else>
      <BackofficeCard
        title="数据口径"
        description="统计只使用当前名册与真实证书数据。"
      >
        <p class="teacher-basis">
          {{ analytics.basis_label }}
        </p>
        <p
          v-if="analytics.no_cert_count > 0"
          class="teacher-no-cert"
        >
          另有 <strong>{{ analytics.no_cert_count }}</strong> 名学员暂无任何证书记录，未计入完成度分布，也不等于 0% 完成。
        </p>
      </BackofficeCard>

      <div class="teacher-analytics-grid">
        <BackofficeCard
          title="完成度分布"
          description="按证书平均完成度分档统计。"
        >
          <div
            class="teacher-bar-chart"
            data-testid="teacher-progress-chart"
          >
            <div
              v-for="item in analytics.progress_distribution"
              :key="item.label"
              class="teacher-bar-row"
            >
              <span class="teacher-bar-label">{{ item.label }}</span>
              <span class="teacher-bar-track">
                <span
                  class="teacher-bar-fill"
                  :style="{ width: progressWidth(item.count) }"
                />
              </span>
              <span class="teacher-bar-value">{{ item.count }} 人</span>
            </div>
          </div>
        </BackofficeCard>

        <BackofficeCard
          title="方向分布"
          description="按学员学习方向统计名册人数。"
        >
          <div
            class="teacher-direction-chart"
            data-testid="teacher-direction-chart"
          >
            <div
              v-for="(item, index) in analytics.direction_distribution"
              :key="item.direction"
              class="teacher-direction-row"
            >
              <span
                class="teacher-direction-dot"
                :class="`is-color-${index % 5}`"
              />
              <span class="teacher-bar-label">{{ item.direction || "未分类" }}</span>
              <span class="teacher-bar-track">
                <span
                  class="teacher-bar-fill"
                  :class="`is-color-${index % 5}`"
                  :style="{ width: directionWidth(item.count) }"
                />
              </span>
              <span class="teacher-bar-value">
                {{ item.count }} 人
              </span>
            </div>
          </div>
        </BackofficeCard>
      </div>

      <BackofficeCard
        title="各方向完成度"
        description="只展示接口真实返回的方向与证书数据。"
      >
        <div
          class="backoffice-table-wrap"
          data-testid="teacher-direction-detail"
        >
          <table class="backoffice-table">
            <thead>
              <tr>
                <th>方向</th>
                <th>学员数</th>
                <th>平均完成度</th>
                <th>已获证书</th>
                <th>暂无证书</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in analytics.direction_progress"
                :key="item.direction"
              >
                <td>{{ item.direction || "未分类" }}</td>
                <td>{{ item.student_count }}</td>
                <td>{{ item.avg_progress.toFixed(1) }}%</td>
                <td>{{ item.cert_earned }}</td>
                <td>{{ item.no_cert_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </BackofficeCard>
    </template>
  </section>
</template>

<style src="./teacher.css"></style>
