<script setup lang="ts">
import { computed, ref } from "vue";

import {
  EC_COPY_FORMATS,
  EC_PRODUCTS,
  generateCopywriting,
  scoreCopywriting,
  submitCopyTraining,
  type CopyFeedback,
  type EcCopyFormat,
} from "@/api/ecommerce";
import { describeApiError } from "@/shared/apiErrors";
import { toMarkdownBlocks } from "@/shared/markdown";

import TrainingHistory from "./TrainingHistory.vue";

const FORMAT_DESCRIPTIONS: Record<EcCopyFormat, string> = {
  详情页: "电商商品详情页文案，层次分明，卖点突出",
  主图文案: "5条独立主图文案，每条8-15字，简洁有力",
  朋友圈: "微信朋友圈推广文案，真实自然，像朋友分享",
  小红书: "小红书种草笔记，种草感强，闺蜜推荐风格",
  短视频脚本: "15-30秒短视频带货脚本，按时间轴输出",
};

const product = ref("荔枝");
const audience = ref("");
const sellingPoints = ref("甜度高、果肉厚、核小、产地直发、冷链保鲜");
const format = ref<EcCopyFormat>("详情页");
const generatedCopy = ref("");
const degraded = ref(false);
const generating = ref(false);
const scoring = ref(false);
const submitting = ref(false);
const myCopy = ref("");
const feedback = ref<CopyFeedback | null>(null);
const scoredCopy = ref("");
const statusMessage = ref("");
const statusKind = ref<"info" | "success" | "warning" | "error">("info");
const historyRefresh = ref(0);

const blocks = computed(() => toMarkdownBlocks(generatedCopy.value));
const feedbackMatches = computed(
  () => Boolean(feedback.value && scoredCopy.value === myCopy.value),
);
const formatDescription = computed(() => FORMAT_DESCRIPTIONS[format.value]);
const scoreMetrics = computed(() => {
  const current = feedback.value;
  if (!current) return [];
  return [
    { label: "结构完整", value: current.structure_score },
    { label: "卖点具体", value: current.selling_score },
    { label: "格式契合", value: current.format_score },
    { label: "合规自检", value: current.compliance_score },
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
  scoredCopy.value = "";
}

function normalizedProduct(): string {
  const raw = product.value.trim();
  return EC_PRODUCTS.find((item) => raw.includes(item)) ?? "荔枝";
}

async function generate(): Promise<void> {
  if (!product.value.trim()) {
    setStatus("请输入产品名称", "warning");
    return;
  }
  generating.value = true;
  generatedCopy.value = "";
  degraded.value = false;
  clearScore();
  setStatus("正在生成商品文案...");
  try {
    const response = await generateCopywriting({
      product: product.value.trim(),
      format: format.value,
      audience: audience.value,
      selling_points: sellingPoints.value.trim(),
    });
    generatedCopy.value = response.copywriting;
    degraded.value = Boolean(response.degraded);
    setStatus(
      degraded.value
        ? "AI 暂不可用，已生成系统内置示例，请改写后再评分。"
        : "商品文案已生成，请改写为你的版本。",
      degraded.value ? "warning" : "success",
    );
  } catch (error) {
    setStatus(describeApiError(error, "生成失败，请稍后重试"), "error");
  } finally {
    generating.value = false;
  }
}

function adopt(): void {
  if (!generatedCopy.value.trim()) {
    setStatus("请先生成 AI 初稿", "warning");
    return;
  }
  myCopy.value = generatedCopy.value;
  clearScore();
  setStatus("初稿已放入「我的稿」，请补全真实信息后评分。", "success");
}

async function copyGenerated(): Promise<void> {
  if (!generatedCopy.value.trim()) {
    setStatus("还没有可复制的文案", "warning");
    return;
  }
  try {
    await navigator.clipboard.writeText(generatedCopy.value);
    setStatus("文案已复制", "success");
  } catch {
    setStatus("复制失败，请手动选择文本", "warning");
  }
}

async function score(): Promise<void> {
  const script = myCopy.value.trim();
  if (!script) {
    setStatus("请先在「我的稿」里写出你的文案", "warning");
    return;
  }
  scoring.value = true;
  setStatus("正在评分...");
  try {
    const response = await scoreCopywriting(script, format.value);
    feedback.value = response.feedback;
    scoredCopy.value = myCopy.value;
    setStatus("文案评分完成", "success");
  } catch (error) {
    clearScore();
    setStatus(describeApiError(error, "评分失败，请稍后重试"), "error");
  } finally {
    scoring.value = false;
  }
}

async function submit(): Promise<void> {
  const script = myCopy.value.trim();
  if (!script) {
    setStatus("请先在「我的稿」里写出你自己的文案", "warning");
    return;
  }
  submitting.value = true;
  setStatus("正在保存实训记录...");
  try {
    const response = await submitCopyTraining({
      product: normalizedProduct(),
      script,
      score: feedbackMatches.value ? feedback.value?.overall_score ?? 0 : 0,
      meta: {
        format: format.value,
        raw_product: product.value.trim(),
      },
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
    id="copywriting-training"
    class="card-section"
    data-testid="copywriting-training"
    aria-labelledby="copywriting-title"
  >
    <h3
      id="copywriting-title"
      class="card-section-title"
    >
      <i
        class="fas fa-edit"
        aria-hidden="true"
      />
      商品文案创作
    </h3>
    <p class="section-desc">
      AI 出初稿，你改写成自己的版本后评分并提交
    </p>

    <div class="copywriting-panel">
      <div class="copywriting-config">
        <div class="copywriting-config-row">
          <div class="form-group">
            <label for="copywriting-product">
              <i
                class="fas fa-box"
                aria-hidden="true"
              />
              文案产品名称
              <span class="hint">（限平台支持的农产品）</span>
            </label>
            <input
              id="copywriting-product"
              v-model="product"
              autocomplete="off"
              placeholder="例如：荔枝"
            >
          </div>
          <div class="form-group">
            <label for="copywriting-audience">
              <i
                class="fas fa-users"
                aria-hidden="true"
              />
              目标人群
            </label>
            <select
              id="copywriting-audience"
              v-model="audience"
            >
              <option value="">
                不限
              </option>
              <option value="家庭采购">
                家庭采购
              </option>
              <option value="注重健康人群">
                注重健康人群
              </option>
              <option value="商务送礼">
                商务送礼
              </option>
              <option value="餐饮商家">
                餐饮商家
              </option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label for="copywriting-points">
            <i
              class="fas fa-star"
              aria-hidden="true"
            />
            核心卖点
            <span class="hint">（用逗号分隔，留空自动生成）</span>
          </label>
          <input
            id="copywriting-points"
            v-model="sellingPoints"
            placeholder="例如：甜度高、果肉厚、核小"
          >
        </div>
      </div>

      <div class="copywriting-formats">
        <span class="form-label">
          <i
            class="fas fa-file-alt"
            aria-hidden="true"
          />
          选择文案格式
        </span>
        <div class="format-tabs">
          <button
            v-for="item in EC_COPY_FORMATS"
            :key="item"
            type="button"
            class="format-tab"
            :class="{ active: format === item }"
            @click="format = item"
          >
            {{ item }}
          </button>
        </div>
        <div class="format-desc">
          {{ formatDescription }}
        </div>
      </div>

      <div class="copywriting-actions">
        <button
          type="button"
          class="btn btn-primary"
          :disabled="generating"
          @click="generate"
        >
          <i
            class="fas"
            :class="generating ? 'fa-spinner fa-spin' : 'fa-magic'"
            aria-hidden="true"
          />
          {{ generating ? "生成中..." : "AI生成文案" }}
        </button>
        <button
          v-if="generatedCopy"
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="generating"
          @click="generate"
        >
          <i
            class="fas fa-redo"
            aria-hidden="true"
          />
          换一版
        </button>
      </div>

      <p
        v-if="statusMessage"
        class="training-submit-info ec-status"
        :class="`is-${statusKind}`"
        data-testid="copywriting-status"
        role="status"
      >
        {{ statusMessage }}
      </p>

      <div
        v-if="generatedCopy"
        class="copywriting-result"
        data-testid="copywriting-result"
      >
        <div class="copywriting-result-header">
          <span class="copywriting-result-tag">
            <i
              class="fas fa-file-alt"
              aria-hidden="true"
            />
            {{ format }}
          </span>
          <span
            v-if="degraded"
            class="copywriting-degraded-tag"
            data-testid="copywriting-degraded"
          >
            <i
              class="fas fa-exclamation-triangle"
              aria-hidden="true"
            />
            系统内置示例，非 AI 生成
          </span>
          <div class="copywriting-result-actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="copyGenerated"
            >
              <i
                class="fas fa-copy"
                aria-hidden="true"
              />
              复制
            </button>
          </div>
        </div>
        <div class="copywriting-result-body">
          <template
            v-for="(block, index) in blocks"
            :key="`${index}-${block.text}`"
          >
            <h3 v-if="block.type === 'heading'">
              {{ block.text }}
            </h3>
            <p
              v-else
              class="copywriting-result-line"
            >
              <span v-if="block.type === 'list'">• </span>{{ block.text }}
            </p>
          </template>
        </div>
      </div>

      <div class="script-block copywriting-mine-block">
        <div class="script-block-title">
          <i
            class="fas fa-pen"
            aria-hidden="true"
          />
          我的稿
          <span class="script-block-sub">（把 AI 初稿改写成你自己的版本后提交）</span>
          <span class="script-block-meta">{{ myCopy.length }} 字</span>
        </div>
        <label
          class="sr-only"
          for="copywriting-mine"
        >文案我的稿</label>
        <textarea
          id="copywriting-mine"
          v-model="myCopy"
          class="script-input"
          rows="8"
          maxlength="4000"
          placeholder="采用初稿后，补上【待填写】里的真实信息，换成你自己的语气。"
        />
        <div class="script-block-note">
          认证、检测数据、价格、物流与赔付承诺不能靠 AI 编造，没有真实信息就保持占位或删除该句。
        </div>
        <div class="script-actions script-actions-submit">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="adopt"
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
            :disabled="scoring"
            @click="score"
          >
            <i
              class="fas"
              :class="scoring ? 'fa-spinner fa-spin' : 'fa-chart-bar'"
              aria-hidden="true"
            />
            {{ scoring ? "评分中..." : "评分我的文案" }}
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
            {{ submitting ? "保存中..." : "提交文案实训" }}
          </button>
        </div>
      </div>

      <div
        v-if="feedback"
        class="copywriting-feedback"
      >
        <div class="copywriting-feedback-head">
          <span
            class="copywriting-feedback-overall"
            data-testid="copywriting-score-overall"
          >{{ feedback.overall_score }}</span>
          <span class="copywriting-feedback-label">文案评分（规则 · 可复现）</span>
        </div>
        <div class="copywriting-feedback-metrics">
          <div
            v-for="metric in scoreMetrics"
            :key="metric.label"
            class="copywriting-feedback-metric"
          >
            <label>{{ metric.label }}</label>
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: `${metric.value}%` }"
              />
            </div>
            <em>{{ metric.value }}</em>
          </div>
        </div>
        <div class="copywriting-feedback-suggestions">
          <div
            v-for="suggestion in feedback.suggestions"
            :key="suggestion"
            class="copywriting-feedback-tip"
          >
            <i
              class="fas fa-lightbulb"
              aria-hidden="true"
            />
            {{ suggestion }}
          </div>
        </div>
      </div>

      <p
        v-if="feedback && !feedbackMatches"
        class="ec-stale-score"
        role="status"
      >
        我的稿已改动，提交时这份旧评分不会计入。
      </p>
    </div>

    <TrainingHistory
      kind="copy"
      title="我的文案实训记录"
      test-id="copywriting-records"
      :refresh-token="historyRefresh"
    />
  </section>
</template>

<style scoped>
.copywriting-panel {
  padding: 24px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  background: var(--bg-secondary);
}

.ec-status {
  margin: 12px 0;
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

.copywriting-result {
  margin-top: 16px;
}

.copywriting-result-line {
  margin: 0 0 8px;
  white-space: pre-wrap;
}

.copywriting-mine-block {
  margin-top: 18px;
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
</style>
