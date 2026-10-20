<script setup lang="ts">
import { computed, ref } from "vue";

import {
  getCustomerServiceHint,
  sendCustomerServiceReply,
  startCustomerService,
  submitCustomerServiceTraining,
  type ServiceHint,
  type ServiceScore,
  type ServiceSentiment,
  type TrainingTurn,
} from "@/api/ecommerce";
import { describeApiError } from "@/shared/apiErrors";

import TrainingHistory from "./TrainingHistory.vue";

interface ChatMessage {
  id: number;
  role: "customer" | "agent" | "system";
  content: string;
  score?: number;
  tips?: string[];
}

const SCENARIOS = [
  "售前咨询",
  "售后处理",
  "投诉应对",
  "议价谈判",
  "产品推荐",
] as const;
const PERSONALITIES = ["友善型", "急躁型", "犹豫型", "挑剔型"] as const;
const DIFFICULTIES = ["新手", "进阶", "挑战"] as const;

const MISSION: Record<string, string> = {
  售前咨询: "耐心解答产品信息，让客户放心下单",
  售后处理: "先安抚情绪，再给出可落地的解决方案",
  投诉应对: "稳住客户情绪，把投诉转为可解决的动作",
  议价谈判: "在不失底线的前提下促成成交",
  产品推荐: "摸清客户需求，精准推荐合适的产品",
};

const PERSONA_HINT: Record<string, string> = {
  友善型: "客户好说话，正常专业即可",
  急躁型: "客户没耐心，回复要快、直给重点",
  犹豫型: "客户反复比较，多给信心和证据",
  挑剔型: "客户爱挑细节，把专业做扎实",
};

const scenario = ref<string>("售前咨询");
const personality = ref<string>("友善型");
const difficulty = ref<string>("进阶");
const product = ref("荔枝");
const started = ref(false);
const starting = ref(false);
const sending = ref(false);
const hinting = ref(false);
const submitting = ref(false);
const reply = ref("");
const messages = ref<ChatMessage[]>([]);
const transcript = ref<TrainingTurn[]>([]);
const scoreHistory = ref<number[]>([]);
const currentScore = ref<ServiceScore | null>(null);
const sentiment = ref<ServiceSentiment>({ level: 60, label: "待开始" });
const hint = ref<ServiceHint | null>(null);
const hintDegraded = ref(false);
const degradedNotice = ref("");
const statusMessage = ref("");
const statusKind = ref<"info" | "success" | "warning" | "error">("info");
const historyRefresh = ref(0);
const review = ref<{ overall: number; rounds: number; scoredRounds: number } | null>(
  null,
);
let nextMessageId = 1;

const missionText = computed(() => MISSION[scenario.value] ?? "");
const personaText = computed(() => PERSONA_HINT[personality.value] ?? "");
const averageScore = computed(() => {
  if (!scoreHistory.value.length) return 0;
  return Math.round(
    scoreHistory.value.reduce((sum, value) => sum + value, 0)
      / scoreHistory.value.length,
  );
});
const scoreDetails = computed(() => {
  const details = currentScore.value?.details;
  if (!details) return [];
  return [
    { label: "礼貌度", value: details.politeness },
    { label: "专业度", value: details.professional },
    { label: "解决力", value: details.solving },
    { label: "同理心", value: details.empathy },
  ];
});

function setStatus(
  message: string,
  kind: "info" | "success" | "warning" | "error" = "info",
): void {
  statusMessage.value = message;
  statusKind.value = kind;
}

function addMessage(
  role: ChatMessage["role"],
  content: string,
  score?: number,
  tips?: string[],
): ChatMessage {
  const message: ChatMessage = {
    id: nextMessageId,
    role,
    content,
    score,
    tips,
  };
  nextMessageId += 1;
  messages.value.push(message);
  return message;
}

function resetConversation(): void {
  messages.value = [];
  transcript.value = [];
  scoreHistory.value = [];
  currentScore.value = null;
  sentiment.value = { level: 60, label: "待开始" };
  hint.value = null;
  hintDegraded.value = false;
  degradedNotice.value = "";
  review.value = null;
  started.value = false;
  reply.value = "";
  statusMessage.value = "";
}

async function start(): Promise<void> {
  resetConversation();
  starting.value = true;
  setStatus("正在生成客户开场白...");
  try {
    const response = await startCustomerService({
      scenario: scenario.value,
      personality: personality.value,
      product: product.value.trim() || "农产品",
    });
    started.value = true;
    addMessage("customer", response.message);
    transcript.value.push({ role: "assistant", content: response.message });
    degradedNotice.value = response.degraded
      ? "系统兜底开场白，非 AI 生成"
      : "";
    setStatus("对话已开始，请作为客服回复客户。", "success");
  } catch (error) {
    started.value = false;
    setStatus(
      describeApiError(error, "生成开场白失败，请稍后重试"),
      "error",
    );
  } finally {
    starting.value = false;
  }
}

async function send(): Promise<void> {
  if (!started.value) {
    setStatus("请先开始模拟", "warning");
    return;
  }
  const text = reply.value.trim();
  if (!text) {
    setStatus("请先输入你的回复", "warning");
    return;
  }

  reply.value = "";
  const agentMessage = addMessage("agent", text);
  sending.value = true;
  setStatus("客户正在回复...");
  try {
    const response = await sendCustomerServiceReply({
      message: text,
      history: transcript.value,
      scenario: scenario.value,
      personality: personality.value,
      difficulty: difficulty.value,
      product: product.value.trim() || "农产品",
    });
    addMessage("customer", response.reply);
    transcript.value.push(
      { role: "user", content: text },
      { role: "assistant", content: response.reply },
    );
    agentMessage.score = response.score.total;
    agentMessage.tips = response.score.tips;
    currentScore.value = response.score;
    scoreHistory.value.push(response.score.total);
    sentiment.value = response.sentiment;
    degradedNotice.value = response.degraded
      ? "系统兜底回复，非 AI 生成，仅供参考"
      : "";
    setStatus("本轮已评分", "success");
  } catch (error) {
    addMessage(
      "system",
      "客户未回应：网络或服务异常，请重试。这条错误不会进入提交记录。",
    );
    setStatus(describeApiError(error, "回复失败，请稍后重试"), "error");
  } finally {
    sending.value = false;
  }
}

async function getHint(): Promise<void> {
  if (!started.value) {
    setStatus("请先开始模拟", "warning");
    return;
  }
  hinting.value = true;
  setStatus("正在分析当前对话...");
  try {
    const lastCustomer = [...transcript.value]
      .reverse()
      .find((turn) => turn.role === "assistant")?.content ?? "";
    const response = await getCustomerServiceHint({
      scenario: scenario.value,
      personality: personality.value,
      product: product.value.trim() || "农产品",
      history: transcript.value,
      last_customer_msg: lastCustomer,
    });
    hint.value = response.hint;
    hintDegraded.value = Boolean(response.degraded);
    setStatus("已获取客服提示", "success");
  } catch (error) {
    hint.value = null;
    setStatus(describeApiError(error, "获取建议失败，请重试"), "error");
  } finally {
    hinting.value = false;
  }
}

function useTemplate(template: string): void {
  reply.value = template;
}

async function submit(): Promise<void> {
  if (!transcript.value.length) {
    setStatus("请先开始并完成至少一轮对话", "warning");
    return;
  }
  submitting.value = true;
  setStatus("正在保存实训记录...");
  const overall = averageScore.value;
  try {
    const response = await submitCustomerServiceTraining({
      product: product.value.trim() || "农产品",
      transcript: transcript.value,
      score: overall,
      meta: {
        scenario: scenario.value,
        personality: personality.value,
        difficulty: difficulty.value,
        rounds: Math.floor(transcript.value.length / 2),
        scored_rounds: scoreHistory.value.length,
      },
    });
    review.value = {
      overall,
      rounds: Math.floor(transcript.value.length / 2),
      scoredRounds: scoreHistory.value.length,
    };
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
    id="customer-service-training"
    class="card-section"
    data-testid="customer-service-training"
    aria-labelledby="customer-service-title"
  >
    <h3
      id="customer-service-title"
      class="card-section-title"
    >
      <i
        class="fas fa-headset"
        aria-hidden="true"
      />
      客户服务模拟
    </h3>
    <p class="section-desc">
      和不同性格的 AI 客户对话，实时评分并获得回复提示
    </p>

    <div class="cs-panel">
      <div class="cs-config">
        <div class="cs-config-row">
          <div class="form-group">
            <label for="cs-scenario">
              <i
                class="fas fa-theater-masks"
                aria-hidden="true"
              />
              模拟场景
            </label>
            <select
              id="cs-scenario"
              v-model="scenario"
            >
              <option
                v-for="item in SCENARIOS"
                :key="item"
                :value="item"
              >
                {{ item }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label for="cs-personality">
              <i
                class="fas fa-user"
                aria-hidden="true"
              />
              客户性格
            </label>
            <select
              id="cs-personality"
              v-model="personality"
            >
              <option
                v-for="item in PERSONALITIES"
                :key="item"
                :value="item"
              >
                {{ item }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label for="cs-difficulty">
              <i
                class="fas fa-signal"
                aria-hidden="true"
              />
              难度
            </label>
            <select
              id="cs-difficulty"
              v-model="difficulty"
            >
              <option
                v-for="item in DIFFICULTIES"
                :key="item"
                :value="item"
              >
                {{ item }}
              </option>
            </select>
          </div>
        </div>
        <div class="cs-config-row">
          <div class="form-group">
            <label for="cs-product">
              <i
                class="fas fa-box"
                aria-hidden="true"
              />
              客服产品
            </label>
            <input
              id="cs-product"
              v-model="product"
              autocomplete="off"
            >
          </div>
          <div class="form-group cs-actions-group">
            <span class="cs-action-label">操作</span>
            <div class="cs-actions">
              <button
                type="button"
                class="btn btn-primary btn-sm"
                :disabled="starting"
                @click="start"
              >
                <i
                  class="fas"
                  :class="starting ? 'fa-spinner fa-spin' : 'fa-play'"
                  aria-hidden="true"
                />
                {{ starting ? "生成中..." : "开始模拟" }}
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                @click="resetConversation"
              >
                <i
                  class="fas fa-redo"
                  aria-hidden="true"
                />
                重置
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="hinting"
                @click="getHint"
              >
                <i
                  class="fas"
                  :class="hinting ? 'fa-spinner fa-spin' : 'fa-lightbulb'"
                  aria-hidden="true"
                />
                {{ hinting ? "分析中..." : "获取客服提示" }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="started"
        class="cs-mission-card"
      >
        <div class="cs-mission-row">
          <span class="cs-mission-tag">{{ scenario }}</span>
          <span class="cs-mission-tag">{{ personality }}</span>
          <span class="cs-mission-tag">{{ difficulty }}</span>
        </div>
        <div class="cs-mission-goal">
          <i
            class="fas fa-flag-checkered"
            aria-hidden="true"
          />
          你的目标：{{ missionText }}
        </div>
        <div class="cs-mission-persona">
          {{ personaText }}
        </div>
      </div>

      <p
        v-if="degradedNotice"
        class="cs-degraded-note"
        data-testid="cs-degraded"
        role="status"
      >
        <i
          class="fas fa-exclamation-triangle"
          aria-hidden="true"
        />
        {{ degradedNotice }}
      </p>

      <div class="cs-chat-area">
        <div class="cs-chat-main">
          <div
            v-if="review"
            class="cs-review-card"
          >
            <div class="cs-review-head">
              <i
                class="fas fa-flag-checkered"
                aria-hidden="true"
              />
              <span>训练复盘</span>
            </div>
            <div class="cs-review-overall">
              <div class="cs-review-score">
                {{ review.overall }}
              </div>
              <div class="cs-review-meta">
                <div class="cs-review-grade">
                  {{ review.overall >= 70 ? "良好" : "继续练习" }}
                </div>
                <div class="cs-review-note">
                  整场 {{ review.rounds }} 轮，{{ review.scoredRounds }} 轮已评分
                </div>
              </div>
            </div>
          </div>

          <div
            class="cs-messages"
            data-testid="cs-messages"
          >
            <div
              v-if="!messages.length"
              class="cs-welcome"
            >
              <i
                class="fas fa-headset"
                aria-hidden="true"
              />
              <p>选择场景和客户性格，点击「开始模拟」进行客服训练</p>
            </div>
            <div
              v-for="message in messages"
              :key="message.id"
              class="cs-msg"
              :class="message.role"
            >
              <div class="cs-msg-avatar">
                <i
                  class="fas"
                  :class="message.role === 'customer'
                    ? 'fa-user'
                    : message.role === 'agent'
                      ? 'fa-headset'
                      : 'fa-exclamation-triangle'"
                  aria-hidden="true"
                />
              </div>
              <div class="cs-msg-content">
                <div class="cs-msg-label">
                  {{ message.role === "customer"
                    ? "客户"
                    : message.role === "agent"
                      ? "你（客服）"
                      : "系统提示" }}
                  <span
                    v-if="message.score !== undefined"
                    class="cs-msg-score"
                  >{{ message.score }}分</span>
                </div>
                <div class="cs-msg-bubble">
                  {{ message.content }}
                </div>
                <div
                  v-if="message.tips?.length"
                  class="cs-msg-reason"
                >
                  {{ message.tips[0] }}
                </div>
              </div>
            </div>
          </div>

          <div class="cs-input-bar">
            <label
              class="sr-only"
              for="cs-input"
            >客服回复</label>
            <input
              id="cs-input"
              v-model="reply"
              :disabled="!started || sending"
              placeholder="作为客服回复客户..."
              @keydown.enter.prevent="send"
            >
            <button
              type="button"
              class="btn btn-primary"
              aria-label="发送客服回复"
              :disabled="!started || sending"
              @click="send"
            >
              <i
                class="fas"
                :class="sending ? 'fa-spinner fa-spin' : 'fa-paper-plane'"
                aria-hidden="true"
              />
            </button>
          </div>

          <div
            v-if="hint?.templates?.length"
            class="cs-quick-chips"
          >
            <span class="cs-quick-chips-label">
              <i
                class="fas fa-bolt"
                aria-hidden="true"
              />
              快捷填充
            </span>
            <button
              v-for="template in hint.templates"
              :key="template"
              type="button"
              class="cs-quick-chip"
              @click="useTemplate(template)"
            >
              {{ template }}
            </button>
          </div>
        </div>

        <aside class="cs-sidebar">
          <div class="cs-score-card">
            <h4>
              <i
                class="fas fa-chart-radar"
                aria-hidden="true"
              />
              实时评分
            </h4>
            <div class="cs-score-note">
              规则关键词评分，逐句分析
            </div>
            <div
              class="cs-score-overall"
              data-testid="cs-score-overall"
            >
              {{ currentScore ? currentScore.total : "-" }}
            </div>
            <div class="cs-score-label">
              本轮得分
            </div>
            <div class="cs-score-bars">
              <div
                v-for="detail in scoreDetails"
                :key="detail.label"
                class="cs-score-bar"
              >
                <span>{{ detail.label }}</span>
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    :style="{ width: `${detail.value}%` }"
                  />
                </div>
                <em>{{ detail.value }}</em>
              </div>
            </div>
          </div>

          <div
            class="cs-tips-card"
            data-testid="cs-hint"
          >
            <h4>
              <i
                class="fas fa-lightbulb"
                aria-hidden="true"
              />
              实时建议
            </h4>
            <div
              v-if="hint"
              class="cs-tips-list"
            >
              <div
                v-if="hint.analysis"
                class="cs-hint-analysis"
              >
                {{ hint.analysis }}
              </div>
              <div
                v-if="hint.strategy"
                class="cs-hint-strategy"
              >
                策略：{{ hint.strategy }}
              </div>
              <div class="cs-hint-section">
                <div class="cs-hint-title">
                  话术参考
                </div>
                <div class="cs-hint-templates">
                  <button
                    v-for="template in hint.templates"
                    :key="template"
                    type="button"
                    class="cs-hint-tpl"
                    @click="useTemplate(template)"
                  >
                    {{ template }}
                  </button>
                </div>
              </div>
              <div
                v-if="hint.tips?.length"
                class="cs-hint-section"
              >
                <div class="cs-hint-title">
                  注意事项
                </div>
                <div
                  v-for="tip in hint.tips"
                  :key="tip"
                  class="cs-tip-item"
                >
                  <i
                    class="fas fa-info-circle"
                    aria-hidden="true"
                  />
                  {{ tip }}
                </div>
              </div>
              <p
                v-if="hintDegraded"
                class="cs-degraded-note"
              >
                以下为系统内置建议，非 AI 生成
              </p>
            </div>
            <div
              v-else
              class="cs-tips-list"
            >
              <div class="cs-tip-item">
                开始对话后可获取建议
              </div>
            </div>
          </div>

          <div class="cs-sentiment-card">
            <h4>
              <i
                class="fas fa-smile"
                aria-hidden="true"
              />
              客户情绪
            </h4>
            <div class="cs-sentiment-label">
              {{ sentiment.label }}
            </div>
            <div class="cs-sentiment-track">
              <div
                class="cs-sentiment-fill"
                :style="{ width: `${sentiment.level}%` }"
              />
            </div>
            <div class="cs-sentiment-scale">
              <span>不满</span><span>满意</span>
            </div>
          </div>

          <div class="cs-history-card">
            <h4>
              <i
                class="fas fa-history"
                aria-hidden="true"
              />
              对话轮次
            </h4>
            <div class="cs-round-count">
              {{ Math.floor(transcript.length / 2) }} 轮
            </div>
            <button
              type="button"
              class="btn btn-outline btn-sm cs-submit-button"
              :disabled="submitting"
              @click="submit"
            >
              <i
                class="fas"
                :class="submitting ? 'fa-spinner fa-spin' : 'fa-paper-plane'"
                aria-hidden="true"
              />
              {{ submitting ? "保存中..." : "提交客服实训" }}
            </button>
          </div>
        </aside>
      </div>

      <p
        v-if="statusMessage"
        class="training-submit-info ec-status"
        :class="`is-${statusKind}`"
        data-testid="cs-status"
        role="status"
      >
        {{ statusMessage }}
      </p>
    </div>

    <TrainingHistory
      kind="cs"
      title="我的客服实训记录"
      test-id="cs-records"
      :refresh-token="historyRefresh"
    />
  </section>
</template>

<style scoped>
.cs-panel {
  padding: 24px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  background: var(--bg-secondary);
}

.cs-actions-group {
  flex: 1;
}

.cs-action-label {
  display: block;
  margin-bottom: 5px;
  color: var(--text-primary);
  font-size: 0.8rem;
  font-weight: 600;
}

.cs-degraded-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 10px 0;
  padding: 8px 12px;
  border: 1px dashed rgba(217, 162, 39, 0.5);
  border-radius: var(--radius-xs);
  background: rgba(217, 162, 39, 0.08);
  color: #a36d00;
  font-size: 0.75rem;
  line-height: 1.5;
}

.cs-msg.system .cs-msg-avatar {
  background: rgba(217, 162, 39, 0.14);
  color: #a36d00;
}

.cs-msg.system .cs-msg-bubble {
  border: 1px dashed rgba(217, 162, 39, 0.5);
  background: rgba(217, 162, 39, 0.08);
  color: #a36d00;
}

.cs-hint-tpl {
  width: 100%;
  text-align: left;
}

.cs-hint-analysis,
.cs-hint-strategy {
  padding: 7px 9px;
  border-radius: var(--radius-xs);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.5;
}

.cs-submit-button {
  width: 100%;
  margin-top: 10px;
}

.ec-status {
  margin: 12px 0 0;
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
