<script setup lang="ts">
import { computed, ref } from "vue";

import {
  EC_PRODUCTS,
  EC_STYLES,
  generateLiveScript,
  scoreLiveScript,
  submitLiveTraining,
  type EcStyle,
  type LiveFeedback,
  type LiveReadingReport,
} from "@/api/ecommerce";
import { describeApiError } from "@/shared/apiErrors";

import LiveSimulation from "./LiveSimulation.vue";
import TrainingHistory from "./TrainingHistory.vue";

const product = ref<string>("荔枝");
const style = ref<EcStyle>("热情");
const generatedScript = ref("");
const degraded = ref(false);
const generating = ref(false);
const scoring = ref(false);
const submitting = ref(false);
const myScript = ref("");
const feedback = ref<LiveFeedback | null>(null);
const scoredScript = ref("");
const liveReport = ref<LiveReadingReport | null>(null);
const liveReportScript = ref("");
const statusMessage = ref("");
const statusKind = ref<"info" | "success" | "warning" | "error">("info");
const historyRefresh = ref(0);

const feedbackMatches = computed(
  () => Boolean(feedback.value && scoredScript.value === myScript.value),
);

const metrics = computed(() => {
  const current = feedback.value;
  if (!current) return [];
  return [
    { label: "语速节奏", key: "speed_score", value: current.speed_score },
    { label: "情绪感染力", key: "emotion_score", value: current.emotion_score },
    { label: "互动技巧", key: "interaction_score", value: current.interaction_score },
    { label: "卖点提炼", key: "selling_score", value: current.selling_score },
  ];
});

function setStatus(
  message: string,
  kind: "info" | "success" | "warning" | "error" = "info",
): void {
  statusMessage.value = message;
  statusKind.value = kind;
}

function clearScore(): void {
  feedback.value = null;
  scoredScript.value = "";
}

function receiveLiveReport(
  report: LiveReadingReport | null,
  script: string,
): void {
  liveReport.value = report;
  liveReportScript.value = report ? script : "";
}

async function generate(): Promise<void> {
  generating.value = true;
  generatedScript.value = "";
  degraded.value = false;
  clearScore();
  setStatus("正在生成 AI 初稿...");
  try {
    const response = await generateLiveScript(product.value, style.value);
    generatedScript.value = response.script;
    degraded.value = Boolean(response.degraded);
    setStatus(
      degraded.value
        ? "AI 暂不可用，已生成系统内置示例，请改写后再评分。"
        : "AI 初稿已生成，请改写为你的直播话术。",
      degraded.value ? "warning" : "success",
    );
  } catch (error) {
    setStatus(describeApiError(error, "生成失败，请稍后重试"), "error");
  } finally {
    generating.value = false;
  }
}

function adoptScript(): void {
  if (!generatedScript.value.trim()) {
    setStatus("请先生成 AI 初稿", "warning");
    return;
  }
  myScript.value = generatedScript.value;
  clearScore();
  setStatus("初稿已放入「我的稿」，请补全真实信息后评分。", "success");
}

async function copyScript(): Promise<void> {
  if (!generatedScript.value.trim()) {
    setStatus("还没有可复制的内容", "warning");
    return;
  }
  try {
    await navigator.clipboard.writeText(generatedScript.value);
    setStatus("初稿已复制", "success");
  } catch {
    setStatus("复制失败，请手动选择文本", "warning");
  }
}

async function score(): Promise<void> {
  const script = myScript.value.trim();
  if (!script) {
    setStatus("请先写出你的直播话术再评分", "warning");
    return;
  }
  scoring.value = true;
  setStatus("正在评分...");
  try {
    const response = await scoreLiveScript(script);
    feedback.value = response.feedback;
    scoredScript.value = myScript.value;
    setStatus("评分完成", "success");
  } catch (error) {
    clearScore();
    setStatus(describeApiError(error, "评分失败，请稍后重试"), "error");
  } finally {
    scoring.value = false;
  }
}

async function submit(): Promise<void> {
  const script = myScript.value.trim();
  if (!script) {
    setStatus("请先写出你的直播话术", "warning");
    return;
  }
  submitting.value = true;
  setStatus("正在保存实训记录...");
  try {
    const response = await submitLiveTraining({
      product: product.value,
      script,
      feedback: feedbackMatches.value ? feedback.value : null,
      report:
        liveReport.value && liveReportScript.value === script
          ? liveReport.value
          : {},
      meta: { style: style.value },
    });
    setStatus(`已保存实训记录（第 ${response.attempts} 次）`, "success");
    historyRefresh.value += 1;
  } catch (error) {
    setStatus(describeApiError(error, "保存失败，请稍后重试"), "error");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section
    id="live-script-training"
    class="live-panel ec-tool-panel"
    data-testid="live-script-training"
    aria-labelledby="live-script-title"
  >
    <div class="panel-header">
      <h3 id="live-script-title">
        <i
          class="fas fa-scroll"
          aria-hidden="true"
        />
        直播带货话术实训
      </h3>
      <span class="ec-tool-note">AI 初稿只作起点，评分与提交以「我的稿」为准</span>
    </div>

    <LiveSimulation
      :product="product"
      :script="myScript"
      @report="receiveLiveReport"
    />

    <div class="live-layout">
      <div class="live-preview">
        <div class="script-toolbar">
          <h4>
            <i
              class="fas fa-magic"
              aria-hidden="true"
            />
            AI 初稿
          </h4>
          <div class="script-style-btns">
            <button
              v-for="item in EC_STYLES"
              :key="item"
              type="button"
              class="style-btn"
              :class="{ active: style === item }"
              @click="style = item"
            >
              {{ item }}型
            </button>
          </div>
        </div>

        <div class="form-group ec-product-select">
          <label for="live-product">直播产品</label>
          <select
            id="live-product"
            v-model="product"
          >
            <option
              v-for="item in EC_PRODUCTS"
              :key="item"
              :value="item"
            >
              {{ item }}
            </option>
          </select>
        </div>

        <div class="script-actions">
          <button
            type="button"
            class="btn btn-success"
            :disabled="generating"
            @click="generate"
          >
            <i
              class="fas"
              :class="generating ? 'fa-spinner fa-spin' : 'fa-magic'"
              aria-hidden="true"
            />
            {{ generating ? "生成中..." : "生成 AI 初稿" }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="adoptScript"
          >
            <i
              class="fas fa-arrow-down"
              aria-hidden="true"
            />
            采用到我的稿
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="copyScript"
          >
            <i
              class="fas fa-copy"
              aria-hidden="true"
            />
            复制
          </button>
        </div>

        <div
          v-if="degraded"
          class="script-degraded"
          data-testid="live-degraded"
        >
          <i
            class="fas fa-exclamation-triangle"
            aria-hidden="true"
          />
          系统内置示例，非 AI 生成
        </div>

        <div class="script-box">
          <p
            v-if="generatedScript"
            class="ec-generated-text"
            data-testid="live-generated-script"
          >
            {{ generatedScript }}
          </p>
          <div
            v-else
            class="script-placeholder"
          >
            <i
              class="fas fa-magic"
              aria-hidden="true"
            />
            <p>选择产品与风格后生成 AI 初稿</p>
          </div>
        </div>
      </div>

      <div class="live-right-panel">
        <div class="live-script-panel">
          <div class="script-block">
            <div class="script-block-title">
              <i
                class="fas fa-pen"
                aria-hidden="true"
              />
              我的稿
              <span class="script-block-sub">（自己改写后提交）</span>
              <span class="script-block-meta">{{ myScript.length }} 字</span>
            </div>
            <label
              class="sr-only"
              for="live-script-mine"
            >直播话术我的稿</label>
            <textarea
              id="live-script-mine"
              v-model="myScript"
              class="script-input"
              rows="8"
              maxlength="3000"
              placeholder="把 AI 初稿按你的想法改写，补全【待填写】里的真实信息。"
            />
            <div class="script-block-note">
              认证、检测数据、价格、物流与赔付承诺不能靠 AI 编造，没有真实信息就保留占位或删除该句。
            </div>
          </div>

          <div class="script-actions script-actions-submit">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="scoring"
              @click="score"
            >
              <i
                class="fas"
                :class="scoring ? 'fa-spinner fa-spin' : 'fa-chart-bar'"
                aria-hidden="true"
              />
              {{ scoring ? "评分中..." : "评分我的话术" }}
            </button>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="submitting"
              @click="submit"
            >
              <i
                class="fas"
                :class="submitting ? 'fa-spinner fa-spin' : 'fa-paper-plane'"
                aria-hidden="true"
              />
              {{ submitting ? "保存中..." : "提交直播实训" }}
            </button>
          </div>

          <p
            v-if="statusMessage"
            class="training-submit-info ec-status"
            :class="`is-${statusKind}`"
            data-testid="live-status"
            role="status"
          >
            {{ statusMessage }}
          </p>
        </div>

        <div class="ai-feedback">
          <div class="feedback-header">
            <h4>
              <i
                class="fas fa-chart-bar"
                aria-hidden="true"
              />
              话术稿评分
              <span class="feedback-sub">（评「我的稿」文本）</span>
            </h4>
          </div>
          <div
            v-if="feedback"
            class="feedback-body"
          >
            <div class="feedback-overall">
              <div
                class="overall-score"
                data-testid="live-score-overall"
              >
                {{ feedback.overall_score }}
              </div>
              <div class="overall-label">
                综合评分
              </div>
            </div>
            <div class="feedback-metrics">
              <div
                v-for="metric in metrics"
                :key="metric.key"
                class="metric"
              >
                <div class="metric-row">
                  <label>{{ metric.label }}</label>
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      :style="{ width: `${metric.value}%` }"
                    />
                  </div>
                  <span>{{ metric.value }}</span>
                </div>
              </div>
            </div>
            <div class="feedback-suggestions">
              <h5>
                <i
                  class="fas fa-lightbulb"
                  aria-hidden="true"
                />
                改进建议
              </h5>
              <div class="suggestions-list">
                <span
                  v-for="suggestion in feedback.suggestions"
                  :key="suggestion"
                  class="suggestion-tag"
                >
                  {{ suggestion }}
                </span>
              </div>
            </div>
            <div class="feedback-summary">
              {{ feedback.summary }}
            </div>
            <div
              class="feedback-source"
              :class="`is-${feedback.source}`"
            >
              <i
                class="fas fa-circle-info"
                aria-hidden="true"
              />
              <span>
                {{ feedback.source === "ai" ? "AI 评分" : "规则评分" }}
                <template v-if="feedback.source_note">
                  ：{{ feedback.source_note }}
                </template>
              </span>
            </div>
          </div>
          <div
            v-else
            class="feedback-placeholder"
          >
            <i
              class="fas fa-chart-simple"
              aria-hidden="true"
            />
            <p>写出「我的稿」后点击「评分我的话术」</p>
          </div>
          <p
            v-if="feedback && !feedbackMatches"
            class="ec-stale-score"
            role="status"
          >
            我的稿已改动，提交时这份旧评分不会计入。
          </p>
        </div>
      </div>
    </div>

    <TrainingHistory
      kind="live"
      title="我的直播实训记录"
      test-id="live-records"
      :refresh-token="historyRefresh"
    />
  </section>
</template>

<style scoped>
.ec-tool-panel {
  margin-top: 30px;
  margin-bottom: 72px;
}

.ec-tool-note {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.ec-product-select {
  margin-bottom: 14px;
}

.ec-product-select label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-primary);
  font-size: 0.82rem;
  font-weight: 600;
}

.ec-product-select select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--bg-primary);
  color: var(--text-primary);
  font: inherit;
}

.script-box {
  margin-top: 14px;
  margin-bottom: 0;
}

.ec-generated-text {
  margin: 0;
  white-space: pre-wrap;
}

.script-degraded {
  margin-top: 12px;
}

.ec-status {
  margin-top: 12px;
  line-height: 1.5;
}

.ec-status.is-success {
  color: #1f6b42;
}

.ec-status.is-warning {
  color: #a36d00;
}

.ec-status.is-error {
  color: #b3382f;
}

.ec-stale-score {
  margin: 12px 0 0;
  color: #a36d00;
  font-size: 0.75rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 900px) {
  .live-layout {
    grid-template-columns: 1fr;
  }
}
</style>
