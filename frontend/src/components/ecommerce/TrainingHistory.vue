<script setup lang="ts">
import { ref, watch } from "vue";

import {
  getTrainingRecords,
  type TrainingKind,
  type TrainingRecord,
} from "@/api/ecommerce";
import { describeApiError } from "@/shared/apiErrors";
import { useSessionStore } from "@/stores/session";

const props = defineProps<{
  kind: TrainingKind;
  title: string;
  testId: string;
  refreshToken: number;
}>();

const session = useSessionStore();
const records = ref<TrainingRecord[]>([]);
const loading = ref(false);
const message = ref("");

function recordExtras(record: TrainingRecord): string {
  return [
    record.meta?.format,
    record.meta?.raw_product,
    record.meta?.scenario,
    record.meta?.personality,
    record.meta?.difficulty,
  ]
    .filter(Boolean)
    .join(" · ");
}

function teacherScore(record: TrainingRecord): string {
  return record.score === null || record.score === undefined
    ? "待老师批改"
    : `${record.score} 分`;
}

function isGraded(record: TrainingRecord): boolean {
  return record.score !== null && record.score !== undefined;
}

function ruleScore(record: TrainingRecord): string {
  return record.rule_score === null || record.rule_score === undefined
    ? "-"
    : `${record.rule_score} 分`;
}

function reportSummary(record: TrainingRecord): string {
  const report = record.report;
  if (!report || report.coverage === undefined) return "";
  const parts = [
    `稿子完成度 ${report.coverage}%`,
    report.speed_cpm !== undefined ? `真实语速 ${report.speed_cpm} 字/分` : "",
    report.rubric_hit !== undefined && report.rubric_total !== undefined
      ? `必卖点命中 ${report.rubric_hit}/${report.rubric_total}`
      : "",
    report.overall_score !== undefined
      ? `朗读分 ${report.overall_score}`
      : "",
  ];
  return parts.filter(Boolean).join(" · ");
}

async function loadRecords(): Promise<void> {
  if (!session.isAuthenticated) {
    records.value = [];
    message.value = "登录后可保存并查看实训记录";
    return;
  }

  loading.value = true;
  message.value = "";
  try {
    const response = await getTrainingRecords(props.kind);
    records.value = response.records;
    if (!records.value.length) message.value = "还没有实训记录";
  } catch (error) {
    records.value = [];
    message.value = describeApiError(error, "加载实训记录失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

watch(
  [() => props.refreshToken, () => session.status],
  () => {
    void loadRecords();
  },
  { immediate: true },
);
</script>

<template>
  <section
    class="live-records"
    :data-testid="testId"
    :aria-label="title"
  >
    <div class="records-header">
      <h4>
        <i
          class="fas fa-list"
          aria-hidden="true"
        />
        {{ title }}
      </h4>
    </div>
    <div class="records-body">
      <p
        v-if="loading"
        class="records-empty"
        role="status"
      >
        加载中...
      </p>
      <p
        v-else-if="message"
        class="records-empty"
        role="status"
      >
        {{ message }}
      </p>
      <template v-else>
        <article
          v-for="record in records"
          :key="record.id"
          class="record-item"
          :data-testid="`training-record-${record.id}`"
        >
          <div class="record-head">
            <strong>{{ record.product || "未填写产品" }}</strong>
            <span class="record-score">教师评分 {{ teacherScore(record) }}</span>
          </div>
          <div class="record-meta">
            第 {{ record.attempts || 1 }} 次
            <template v-if="record.submitted_at">
              · {{ record.submitted_at }}
            </template>
            <template v-if="recordExtras(record)">
              · {{ recordExtras(record) }}
            </template>
            · {{ record.status_label }}
            · 系统规则分 {{ ruleScore(record) }}
          </div>
          <div
            v-if="reportSummary(record)"
            class="record-meta record-reading"
          >
            {{ reportSummary(record) }}
          </div>
          <p
            v-if="!isGraded(record)"
            class="record-pending"
          >
            教师尚未批改，提交后等待教师反馈。
          </p>
          <div
            v-if="record.feedback"
            class="record-feedback"
          >
            教师评语：{{ record.feedback }}
          </div>
        </article>
      </template>
    </div>
  </section>
</template>

<style scoped>
.record-reading {
  color: var(--accent-blue);
}

.record-pending {
  margin: 6px 0 0;
  color: #a36d00;
  font-size: 0.74rem;
  line-height: 1.5;
}
</style>
