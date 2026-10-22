<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  getTeacherTrainings,
  gradeTeacherTraining,
  type TeacherTraining,
} from "@/api/teacher";
import BackofficeCard from "@/components/backoffice/BackofficeCard.vue";
import BackofficeFeedback from "@/components/backoffice/BackofficeFeedback.vue";
import BackofficeState from "@/components/backoffice/BackofficeState.vue";

const trainings = ref<TeacherTraining[]>([]);
const pendingRegrade = ref(0);
const loading = ref(true);
const loadError = ref("");
const feedback = ref<{ kind: "success" | "error"; message: string } | null>(
  null,
);
const selected = ref<TeacherTraining | null>(null);
const gradeScore = ref<string | number>("");
const gradeFeedback = ref("");
const gradeError = ref("");
const grading = ref(false);

const selectedTitle = computed(() => {
  if (!selected.value) return "批改实训";
  return `批改实训 · ${kindLabel(selected.value.kind)} · ${selected.value.product || "未命名作品"}`;
});

function kindLabel(kind: string): string {
  return (
    {
      live: "直播带货",
      copy: "商品文案",
      cs: "客服对练",
    }[kind] || kind || "实训"
  );
}

function errorMessage(value: unknown, fallback: string): string {
  if (value instanceof ApiError || value instanceof Error) {
    return value.message || fallback;
  }
  return fallback;
}

function displayNumber(value: number | null): string {
  return value === null || value === undefined ? "未批改" : String(value);
}

function statusClass(status: string): string {
  if (status === "graded") return "is-graded";
  if (status === "resubmitted") return "is-regrade";
  return "is-pending";
}

async function loadTrainings(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    const result = await getTeacherTrainings();
    trainings.value = result.trainings;
    pendingRegrade.value = result.pending_regrade;
  } catch (requestError) {
    trainings.value = [];
    pendingRegrade.value = 0;
    loadError.value = errorMessage(requestError, "实训提交加载失败");
  } finally {
    loading.value = false;
  }
}

function openGrade(training: TeacherTraining): void {
  selected.value = training;
  gradeScore.value =
    training.score === null || training.score === undefined
      ? ""
      : String(training.score);
  gradeFeedback.value = training.feedback || "";
  gradeError.value = "";
}

function closeGrade(): void {
  if (grading.value) return;
  selected.value = null;
  gradeError.value = "";
}

async function submitGrade(): Promise<void> {
  const training = selected.value;
  if (!training) return;
  gradeError.value = "";
  const raw = String(gradeScore.value).trim();
  const score = Number(raw);
  if (!raw || !Number.isInteger(score) || score < 0 || score > 100) {
    gradeError.value = "分数需为 0-100 的整数";
    return;
  }
  grading.value = true;
  try {
    const response = await gradeTeacherTraining({
      submission_id: training.id,
      score,
      feedback: gradeFeedback.value.trim(),
    });
    selected.value = null;
    feedback.value = {
      kind: "success",
      message: response.message || "批改成功",
    };
    await loadTrainings();
  } catch (requestError) {
    gradeError.value = errorMessage(requestError, "批改失败，请稍后重试");
  } finally {
    grading.value = false;
  }
}

onMounted(loadTrainings);
</script>

<template>
  <section class="backoffice-page">
    <header class="backoffice-page-header">
      <div>
        <p>教学工作</p>
        <h1>实训提交</h1>
        <span>先查看学员作品，再填写分数与评语。系统规则分与教师评分分开显示。</span>
      </div>
      <button
        type="button"
        class="backoffice-button is-secondary"
        :disabled="loading"
        @click="loadTrainings"
      >
        <i
          class="fas fa-rotate"
          :class="{ 'fa-spin': loading }"
          aria-hidden="true"
        />
        刷新
      </button>
    </header>

    <BackofficeFeedback
      v-if="feedback"
      :kind="feedback.kind"
      :message="feedback.message"
      testid="teacher-trainings-feedback"
    />

    <div
      v-if="pendingRegrade > 0"
      class="teacher-regrade-notice"
      data-testid="teacher-pending-regrade"
    >
      有 {{ pendingRegrade }} 条实训被学员重新提交，之前的评分与评语已保留，请重新复核。
    </div>

    <BackofficeState
      v-if="loading"
      kind="loading"
      title="正在加载实训提交"
    />
    <BackofficeState
      v-else-if="loadError"
      kind="error"
      title="实训提交加载失败"
      :detail="loadError"
    >
      <button
        type="button"
        class="backoffice-button"
        @click="loadTrainings"
      >
        重试
      </button>
    </BackofficeState>
    <BackofficeState
      v-else-if="!trainings.length"
      kind="empty"
      title="暂无学员实训提交"
      detail="学员提交直播、文案或客服实训后，会出现在这里。"
    />
    <BackofficeCard
      v-else
      flush
    >
      <div class="backoffice-table-wrap">
        <table class="backoffice-table teacher-training-table">
          <thead>
            <tr>
              <th>学员</th>
              <th>类型</th>
              <th>产品</th>
              <th>提交次数</th>
              <th>系统规则分</th>
              <th>我的评分</th>
              <th>状态</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="training in trainings"
              :key="training.id"
              data-testid="teacher-training-row"
              :data-submission-id="training.id"
              :class="{ 'is-regrade': training.regrade_needed }"
            >
              <td>
                <strong>{{ training.student_name || training.student_id }}</strong>
                <small v-if="training.student_name">{{ training.student_id }}</small>
              </td>
              <td>
                <strong>{{ kindLabel(training.kind) }}</strong>
                <small>
                  {{
                    training.kind === "cs"
                      ? training.transcript.length
                        ? `对话 ${training.transcript.length} 条`
                        : "无对话记录"
                      : training.script
                        ? `正文 ${training.script_len} 字`
                        : "无正文"
                  }}
                </small>
              </td>
              <td>{{ training.product || "未填写" }}</td>
              <td>{{ training.attempts || 1 }}</td>
              <td>{{ displayNumber(training.rule_score) }}</td>
              <td>
                <strong>{{ displayNumber(training.score) }}</strong>
                <small v-if="training.feedback">
                  {{ training.feedback }}
                </small>
              </td>
              <td>
                <span
                  class="teacher-training-status"
                  :class="statusClass(training.status)"
                >
                  {{ training.status_label || "待批改" }}
                </span>
              </td>
              <td>{{ training.submitted_at || "未记录" }}</td>
              <td>
                <button
                  type="button"
                  class="backoffice-button is-small is-secondary"
                  data-testid="teacher-training-open"
                  @click="openGrade(training)"
                >
                  {{ training.status === "graded" ? "查看 / 重批" : "查看并批改" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </BackofficeCard>

    <Teleport to="body">
      <div
        v-if="selected"
        class="backoffice-modal-overlay"
        @click.self="closeGrade"
      >
        <form
          class="backoffice-modal teacher-grade-modal"
          data-testid="teacher-grade-dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="selectedTitle"
          @submit.prevent="submitGrade"
        >
          <header class="backoffice-modal-head">
            <div>
              <p>实训批改</p>
              <h2>{{ selectedTitle }}</h2>
            </div>
            <button
              type="button"
              class="backoffice-icon-button"
              aria-label="关闭"
              @click="closeGrade"
            >
              <i
                class="fas fa-xmark"
                aria-hidden="true"
              />
            </button>
          </header>
          <div class="backoffice-modal-body">
            <p class="teacher-grade-meta">
              学员：<strong>{{ selected.student_name || selected.student_id }}</strong>
              · 第 {{ selected.attempts || 1 }} 次提交
              · {{ selected.submitted_at || "提交时间未记录" }}
              · 系统规则分：{{ displayNumber(selected.rule_score) }}
              <template v-if="selected.graded_at">
                · 上次批改：{{ selected.graded_at }}
              </template>
            </p>

            <div class="teacher-work-label">
              学员提交的作品
            </div>
            <div
              v-if="selected.kind === 'cs' && selected.transcript.length"
              class="teacher-transcript"
            >
              <div
                v-for="(turn, index) in selected.transcript"
                :key="`${index}-${turn.role}`"
                class="teacher-transcript-row"
                :class="{ 'is-student': turn.role === 'user' }"
              >
                <span class="teacher-transcript-who">
                  {{ turn.role === "user" ? "学员" : "客户" }}
                </span>
                <span>{{ turn.content }}</span>
              </div>
            </div>
            <pre
              v-else-if="selected.script"
              class="teacher-work-script"
            >{{ selected.script }}</pre>
            <p
              v-else
              class="backoffice-muted"
            >
              该条提交没有可展示的正文，可能是早期版本留下的记录。
            </p>

            <BackofficeFeedback
              v-if="gradeError"
              kind="error"
              :message="gradeError"
              testid="teacher-grade-error"
            />
            <label class="backoffice-field">
              <span>我的评分（0-100）</span>
              <input
                v-model="gradeScore"
                type="number"
                min="0"
                max="100"
                step="1"
                required
              >
            </label>
            <label class="backoffice-field">
              <span>评语（可留空，学员会在消息中心看到）</span>
              <textarea
                v-model="gradeFeedback"
                rows="4"
              />
            </label>
          </div>
          <footer class="backoffice-modal-actions">
            <button
              type="button"
              class="backoffice-button is-secondary"
              :disabled="grading"
              @click="closeGrade"
            >
              取消
            </button>
            <button
              type="button"
              class="backoffice-button"
              :disabled="grading"
              @click="submitGrade"
            >
              {{ grading ? "提交中..." : "确认批改" }}
            </button>
          </footer>
        </form>
      </div>
    </Teleport>
  </section>
</template>

<style src="./teacher.css"></style>
