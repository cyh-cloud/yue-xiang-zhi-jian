<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import {
  getAgricultureSuggestions,
  streamAgricultureQuestion,
  type AgricultureQuestionHistory,
} from "@/api/agriculture";
import { ApiError } from "@/api/client";

interface QaRound {
  id: number;
  question: string;
  answer: string;
  suggestions: string[];
  status: "streaming" | "done" | "error";
  error: string;
}

const props = defineProps<{
  productId: string;
  productName: string;
  sessionId: string;
}>();

const QUESTION_MAX_LENGTH = 500;
const HISTORY_TURNS = 5;

const question = ref("");
const rounds = ref<QaRound[]>([]);
const suggestions = ref<string[]>([]);
const isTyping = ref(false);
const inputFeedback = ref("");
let roundSequence = 0;
let suggestionSequence = 0;
let activeController: AbortController | null = null;

const currentProductId = computed(() => props.productId || "lychee");
const currentProductName = computed(() => props.productName || "广东特色农产品");

watch(
  currentProductId,
  () => {
    resetConversation();
    void loadSuggestions();
  },
  { immediate: true },
);

watch(currentProductName, () => {
  void loadSuggestions();
});

onBeforeUnmount(() => {
  activeController?.abort();
});

async function loadSuggestions(): Promise<void> {
  const sequence = ++suggestionSequence;
  try {
    const response = await getAgricultureSuggestions(currentProductId.value);
    if (sequence !== suggestionSequence) return;
    suggestions.value = response.suggestions.filter(
      (item) => item.trim().length > 0,
    );
  } catch {
    if (sequence !== suggestionSequence) return;
    suggestions.value = [];
  }
  if (!suggestions.value.length) {
    suggestions.value = [
      `${currentProductName.value}当前季节该做哪些管理？`,
      `${currentProductName.value}常见病虫害如何防治？`,
      `${currentProductName.value}怎么提高产量和品质？`,
    ];
  }
}

async function sendQuestion(rawQuestion?: string): Promise<void> {
  const nextQuestion = (rawQuestion ?? question.value).trim();
  inputFeedback.value = "";
  if (!nextQuestion) {
    inputFeedback.value = "请输入农业问题后再发送。";
    return;
  }
  if (nextQuestion.length > QUESTION_MAX_LENGTH) {
    inputFeedback.value = `问题过长，请控制在 ${QUESTION_MAX_LENGTH} 字以内。`;
    return;
  }
  if (isTyping.value) {
    inputFeedback.value = "正在回答上一个问题，请稍候再问。";
    return;
  }

  const round: QaRound = {
    id: ++roundSequence,
    question: nextQuestion,
    answer: "",
    suggestions: [],
    status: "streaming",
    error: "",
  };
  rounds.value.push(round);
  question.value = "";
  isTyping.value = true;

  const controller = new AbortController();
  activeController = controller;
  try {
    await streamAgricultureQuestion(
      {
        question: nextQuestion,
        product: currentProductId.value,
        history: historyPayload(),
      },
      props.sessionId,
      {
        onContent(content) {
          round.answer += content;
        },
        onDone() {
          round.status = "done";
          isTyping.value = false;
        },
        onSuggestions(items) {
          round.suggestions = items;
        },
      },
      controller.signal,
    );
    if (round.status === "streaming") round.status = "done";
  } catch (error) {
    if (isAbortError(error)) return;
    const message =
      error instanceof ApiError
        ? error.message
        : "AI 服务暂时不可用，请稍后重试。";
    round.error = message;
    round.status = round.answer.trim() ? "done" : "error";
  } finally {
    if (activeController === controller) activeController = null;
    isTyping.value = false;
    void loadSuggestions();
  }
}

function retryRound(round: QaRound): void {
  rounds.value = rounds.value.filter((item) => item.id !== round.id);
  void sendQuestion(round.question);
}

function resetConversation(): void {
  activeController?.abort();
  activeController = null;
  rounds.value = [];
  question.value = "";
  inputFeedback.value = "";
  isTyping.value = false;
}

function clearConversation(): void {
  resetConversation();
  void loadSuggestions();
}

function handleQuestionKeydown(event: KeyboardEvent): void {
  if (
    event.key === "Enter" &&
    !event.shiftKey &&
    !event.isComposing
  ) {
    event.preventDefault();
    void sendQuestion();
  }
}

function historyPayload(): AgricultureQuestionHistory[] {
  return rounds.value
    .filter((round) => round.status === "done" && round.answer.trim())
    .slice(-HISTORY_TURNS)
    .map((round) => ({
      question: round.question,
      answer: round.answer,
    }));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
</script>

<template>
  <section
    id="agriculture-qa-section"
    class="card-section"
    aria-labelledby="agriculture-qa-title"
  >
    <h3
      id="agriculture-qa-title"
      class="card-section-title"
    >
      <i
        class="fas fa-robot"
        aria-hidden="true"
      />
      AI农技问答
    </h3>

    <div class="qa-chat-wrap">
      <div
        class="qa-chat-flow"
        aria-live="polite"
      >
        <div
          v-if="!rounds.length"
          class="qa-welcome"
        >
          <i
            class="fas fa-robot"
            aria-hidden="true"
          />
          <p>
            你好！我是AI农技专家，专注于
            <strong>{{ currentProductName }}</strong>
            种植指导。有什么问题尽管问我！
          </p>
        </div>

        <div
          v-for="round in rounds"
          :key="round.id"
          class="qa-round"
        >
          <div class="qa-message user">
            <div
              class="msg-avatar"
              aria-hidden="true"
            >
              <i class="fas fa-user" />
            </div>
            <div class="msg-bubble">
              {{ round.question }}
            </div>
          </div>

          <div
            v-if="round.answer"
            class="qa-message bot"
            data-testid="qa-answer"
          >
            <div
              class="msg-avatar"
              aria-hidden="true"
            >
              <i class="fas fa-robot" />
            </div>
            <div class="msg-bubble">
              <div class="qa-msg-content">
                {{ round.answer }}
              </div>
              <p
                v-if="round.error"
                class="qa-inline-note"
                role="status"
              >
                回答中断：{{ round.error }}
              </p>
            </div>
          </div>

          <div
            v-else-if="round.status === 'streaming'"
            class="qa-message bot"
            role="status"
          >
            <div
              class="msg-avatar"
              aria-hidden="true"
            >
              <i class="fas fa-robot" />
            </div>
            <div class="qa-typing">
              <div
                class="qa-typing-dots"
                aria-hidden="true"
              >
                <span />
                <span />
                <span />
              </div>
              <span>思考中...</span>
            </div>
          </div>

          <div
            v-else-if="round.status === 'error'"
            class="qa-message bot qa-message-error"
            role="alert"
          >
            <div
              class="msg-avatar"
              aria-hidden="true"
            >
              <i class="fas fa-robot" />
            </div>
            <div class="msg-bubble">
              <div class="error-state">
                <i
                  class="fas fa-triangle-exclamation"
                  aria-hidden="true"
                />
                <p>{{ round.error }}</p>
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  @click="retryRound(round)"
                >
                  重新提问
                </button>
              </div>
            </div>
          </div>

          <p
            v-if="round.status === 'done'"
            class="qa-inline-note"
          >
            <i
              class="fas fa-circle-check"
              aria-hidden="true"
            />
            回答完成
          </p>

          <div
            v-if="round.suggestions.length"
            class="qa-msg-suggestions"
          >
            <div class="qa-msg-actions">
              <button
                v-for="item in round.suggestions"
                :key="item"
                type="button"
                class="qa-action-btn suggest-btn"
                :disabled="isTyping"
                @click="sendQuestion(item)"
              >
                <i
                  class="fas fa-reply"
                  aria-hidden="true"
                />
                {{ item }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div
        class="qa-suggestions"
        aria-label="推荐问题"
      >
        <button
          v-for="item in suggestions"
          :key="item"
          type="button"
          class="example-btn"
          :disabled="isTyping"
          @click="sendQuestion(item)"
        >
          {{ item }}
        </button>
      </div>

      <div class="qa-input-bar">
        <textarea
          v-model="question"
          rows="1"
          :maxlength="QUESTION_MAX_LENGTH"
          aria-label="输入你的农业问题"
          placeholder="输入你的农业问题..."
          @keydown="handleQuestionKeydown"
        />
        <button
          type="button"
          class="btn btn-primary"
          aria-label="发送"
          :disabled="isTyping"
          @click="sendQuestion()"
        >
          <i
            class="fas fa-paper-plane"
            aria-hidden="true"
          />
        </button>
      </div>

      <p
        v-if="inputFeedback"
        class="qa-inline-note"
        role="status"
      >
        {{ inputFeedback }}
      </p>

      <p
        class="qa-disclaimer"
        role="note"
      >
        <i
          class="fas fa-shield-alt"
          aria-hidden="true"
        />
        <span>
          回答由 AI 自动生成，仅供参考。农药、兽药的使用种类与用量请以产品标签和当地农技站指导为准；
          涉及改种、大面积施药等重大决策，请多方核实后再执行。
        </span>
      </p>

      <div class="qa-toolbar">
        <button
          type="button"
          class="qa-toolbar-btn"
          @click="clearConversation"
        >
          <i
            class="fas fa-trash-alt"
            aria-hidden="true"
          />
          清空对话
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.qa-msg-content {
  white-space: pre-wrap;
}

.qa-inline-note {
  margin: 6px 0 0;
}

.qa-message .error-state {
  display: grid;
  justify-items: start;
  gap: 8px;
}
</style>
