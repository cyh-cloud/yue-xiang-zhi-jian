<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

import {
  askDialectVoice,
  getDialectInfo,
  getDialects,
  type DialectInfo,
  type DialectPhrase,
  type DialectSummary,
  type DialectVoiceHistory,
  type DialectVoiceResult,
} from "@/api/resources";

interface SpeechResultAlternative {
  transcript: string;
}

interface SpeechResult {
  isFinal: boolean;
  0: SpeechResultAlternative;
}

interface SpeechResultList {
  length: number;
  [index: number]: SpeechResult;
}

interface SpeechResultEvent {
  results: SpeechResultList;
}

interface SpeechErrorEvent {
  error: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface ChatEntry {
  id: number;
  role: "user" | "bot";
  text: string;
  result?: DialectVoiceResult;
  error?: boolean;
}

const props = defineProps<{
  initialDialect?: string;
}>();

const DIALECT_SPEECH_LANG: Readonly<Record<string, string>> = {
  cantonese: "zh-HK",
  hakka: "zh-CN",
  teochew: "zh-CN",
};

const DIALECT_TTS_LANG = DIALECT_SPEECH_LANG;
const MAX_HISTORY = 10;

const dialects = ref<DialectSummary[]>([]);
const dialectsLoading = ref(true);
const dialectsError = ref("");
const selectedDialect = ref(props.initialDialect || "cantonese");
const info = ref<DialectInfo | null>(null);
const infoLoading = ref(false);
const infoError = ref("");
const chat = ref<ChatEntry[]>([]);
const input = ref("");
const sending = ref(false);
const voiceHint = ref("");
const recording = ref(false);
const speakingId = ref<number | null>(null);
const ttsState = ref<"idle" | "speaking" | "paused">("idle");
const messagesElement = ref<HTMLElement | null>(null);

let recognition: SpeechRecognitionLike | null = null;
let messageId = 0;
let infoSequence = 0;
let hintTimer: number | undefined;
let utterance: SpeechSynthesisUtterance | null = null;
let keepAliveTimer: number | undefined;

const currentName = computed(
  () =>
    dialects.value.find((dialect) => dialect.id === selectedDialect.value)
      ?.name ??
    info.value?.name ??
    "该方言",
);
const history = computed<DialectVoiceHistory[]>(() =>
  chat.value
    .filter(
      (entry): entry is ChatEntry & { role: "bot"; result: DialectVoiceResult } =>
        entry.role === "bot" && Boolean(entry.result),
    )
    .map((entry) => ({
      user:
        chat.value[chat.value.indexOf(entry) - 1]?.text ??
        entry.result.text,
      bot: entry.result.answer,
    }))
    .slice(-MAX_HISTORY),
);

const speechConstructor = computed<SpeechRecognitionConstructor | null>(() => {
  const speechWindow = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return (
    speechWindow.SpeechRecognition ??
    speechWindow.webkitSpeechRecognition ??
    null
  );
});

watch(
  selectedDialect,
  (dialect) => {
    void loadDialect(dialect);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopRecording();
  stopSpeaking();
  if (hintTimer !== undefined) window.clearTimeout(hintTimer);
});

void loadDialects();

async function loadDialects(): Promise<void> {
  dialectsLoading.value = true;
  dialectsError.value = "";
  try {
    const response = await getDialects();
    dialects.value = response.dialects;
    if (
      response.dialects.length &&
      !response.dialects.some(
        (dialect) => dialect.id === selectedDialect.value,
      )
    ) {
      selectedDialect.value = response.dialects[0]?.id ?? "cantonese";
    }
  } catch {
    dialects.value = [];
    dialectsError.value = "方言目录加载失败，请检查网络后重试";
  } finally {
    dialectsLoading.value = false;
  }
}

async function loadDialect(dialectId: string): Promise<void> {
  const sequence = ++infoSequence;
  infoLoading.value = true;
  infoError.value = "";
  info.value = null;
  clearChat();
  try {
    const response = await getDialectInfo(dialectId);
    if (sequence !== infoSequence) return;
    if (!response.success || response.info.id !== dialectId) {
      infoError.value = `${currentName.value}的资料暂时取不到，请重新选择该方言重试`;
      return;
    }
    info.value = response.info;
  } catch {
    if (sequence !== infoSequence) return;
    infoError.value = `${currentName.value}的资料暂时取不到，请检查网络后重试`;
  } finally {
    if (sequence === infoSequence) infoLoading.value = false;
  }
}

function selectDialect(dialectId: string): void {
  if (dialectId === selectedDialect.value) return;
  selectedDialect.value = dialectId;
}

function selectPhrase(phrase: DialectPhrase): void {
  void send(phrase.dialect);
}

async function send(text = input.value): Promise<void> {
  const value = text.trim();
  if (!value || sending.value || !info.value) return;
  stopSpeaking();
  chat.value.push({ id: ++messageId, role: "user", text: value });
  if (text === input.value) input.value = "";
  const pendingId = ++messageId;
  chat.value.push({ id: pendingId, role: "bot", text: "思考中..." });
  sending.value = true;
  await scrollMessages();
  try {
    const result = await askDialectVoice({
      text: value,
      dialect: selectedDialect.value,
      history: history.value,
    });
    replaceEntry(pendingId, {
      id: pendingId,
      role: "bot",
      text: result.answer || "暂无回答",
      result,
    });
  } catch (error) {
    replaceEntry(pendingId, {
      id: pendingId,
      role: "bot",
      text: voiceErrorText(error),
      error: true,
    });
  } finally {
    sending.value = false;
    await scrollMessages();
  }
}

function replaceEntry(id: number, entry: ChatEntry): void {
  const index = chat.value.findIndex((item) => item.id === id);
  if (index >= 0) chat.value[index] = entry;
}

function voiceErrorText(error: unknown): string {
  if (isErrorWithStatus(error, 429)) {
    return "提问过于频繁，请稍后再试";
  }
  if (isErrorWithCode(error, "ai_not_configured")) {
    return "该功能尚未启用，请联系管理员";
  }
  if (isErrorWithCode(error, "network_error")) {
    return "无法连接方言问答服务，请检查网络后重试";
  }
  return "抱歉，暂时无法回答，请稍后再试";
}

function isErrorWithStatus(error: unknown, status: number): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === status
  );
}

function isErrorWithCode(error: unknown, code: string): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === code
  );
}

async function scrollMessages(): Promise<void> {
  await nextTick();
  if (messagesElement.value) {
    messagesElement.value.scrollTop = messagesElement.value.scrollHeight;
  }
}

function clearChat(): void {
  stopSpeaking();
  chat.value = [];
}

function setVoiceHint(message: string): void {
  voiceHint.value = message;
  if (hintTimer !== undefined) window.clearTimeout(hintTimer);
  hintTimer = window.setTimeout(() => {
    voiceHint.value = "";
    hintTimer = undefined;
  }, 6_000);
}

function toggleRecording(): void {
  if (recording.value) {
    stopRecording();
    return;
  }
  const Constructor = speechConstructor.value;
  if (!Constructor) {
    setVoiceHint("当前浏览器不支持语音识别，请改用文字输入提问");
    return;
  }
  const instance = new Constructor();
  instance.lang = DIALECT_SPEECH_LANG[selectedDialect.value] ?? "zh-CN";
  instance.continuous = false;
  instance.interimResults = true;
  instance.onresult = (event) => {
    const result = event.results[0];
    if (!result) return;
    input.value = result[0]?.transcript ?? "";
    if (result.isFinal) {
      void send(input.value);
      input.value = "";
      stopRecording();
    }
  };
  instance.onerror = (event) => {
    const messages: Record<string, string> = {
      "not-allowed":
        "麦克风权限被拒绝，请在浏览器地址栏允许麦克风后重试",
      "service-not-allowed":
        "麦克风权限被拒绝，请在浏览器地址栏允许麦克风后重试",
      "audio-capture": "未检测到麦克风设备，请确认麦克风已连接",
      "no-speech": "没有听到声音，请靠近麦克风再试一次",
      network: "语音识别网络异常，请检查网络后重试",
    };
    const message = messages[event.error] ?? `语音识别失败：${event.error}`;
    setVoiceHint(message);
    stopRecording();
  };
  instance.onend = () => {
    recording.value = false;
    recognition = null;
  };
  recognition = instance;
  recording.value = true;
  voiceHint.value = "";
  try {
    instance.start();
  } catch {
    recording.value = false;
    recognition = null;
    setVoiceHint("无法启动语音识别，请改用文字输入提问");
  }
}

function stopRecording(): void {
  recording.value = false;
  if (!recognition) return;
  try {
    recognition.stop();
  } catch {
    // The browser may already have ended the session.
  }
  recognition = null;
}

function speak(entry: ChatEntry): void {
  if (!entry.result) return;
  if (!("speechSynthesis" in window)) {
    setVoiceHint("当前浏览器不支持语音朗读");
    return;
  }
  if (speakingId.value === entry.id) {
    if (ttsState.value === "speaking") {
      window.speechSynthesis.pause();
      ttsState.value = "paused";
      return;
    }
    if (ttsState.value === "paused") {
      window.speechSynthesis.resume();
      ttsState.value = "speaking";
      return;
    }
  }
  stopSpeaking();
  const text = entry.result.answer.replace(/[*_`#>[\]]/g, "").trim();
  if (!text) return;
  const next = new SpeechSynthesisUtterance(text);
  next.lang = DIALECT_TTS_LANG[selectedDialect.value] ?? "zh-CN";
  next.rate = 0.95;
  next.onend = () => {
    if (utterance === next) stopSpeaking();
  };
  next.onerror = () => {
    if (utterance === next) stopSpeaking();
  };
  utterance = next;
  speakingId.value = entry.id;
  ttsState.value = "speaking";
  window.speechSynthesis.speak(next);
  keepAliveTimer = window.setInterval(() => {
    if (ttsState.value === "speaking") window.speechSynthesis.resume();
  }, 10_000);
}

function stopSpeaking(): void {
  if (keepAliveTimer !== undefined) {
    window.clearInterval(keepAliveTimer);
    keepAliveTimer = undefined;
  }
  if ("speechSynthesis" in window) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // The speech engine may already be idle.
    }
  }
  utterance = null;
  speakingId.value = null;
  ttsState.value = "idle";
}

function sourceNote(entry: ChatEntry): string {
  return entry.result?.source === "fallback"
    ? "本地方言语料库回答，仅供学习参考"
    : "AI 方言回答，仅供学习参考，个别用词可能与当地口语有差异";
}
</script>

<template>
  <section
    class="card-section dialect-section resources-dialect"
    aria-labelledby="dialect-title"
  >
    <h2
      id="dialect-title"
      class="card-section-title"
    >
      <i
        class="fas fa-microphone"
        aria-hidden="true"
      />
      方言语音交互
    </h2>

    <div
      v-if="dialectsError"
      class="resources-state resources-state-error"
      role="alert"
    >
      {{ dialectsError }}
      <button
        type="button"
        class="btn btn-outline btn-sm"
        @click="loadDialects"
      >
        重新加载
      </button>
    </div>
    <div
      v-else-if="dialectsLoading"
      class="resources-state"
      role="status"
    >
      方言目录加载中…
    </div>
    <div
      v-if="dialects.length"
      class="dialect-cards"
    >
      <button
        v-for="dialect in dialects"
        :key="dialect.id"
        type="button"
        class="dialect-card"
        :class="{ active: dialect.id === selectedDialect }"
        :aria-pressed="dialect.id === selectedDialect"
        @click="selectDialect(dialect.id)"
      >
        <span class="dialect-card-header">
          <span class="dialect-emoji">{{ dialect.emoji }}</span>
          <span>
            <strong>{{ dialect.name }}</strong>
            <span>{{ dialect.region }}</span>
          </span>
        </span>
        <span class="dialect-card-meta">
          <span>
            <i
              class="fas fa-map-marker-alt"
              aria-hidden="true"
            />
            {{ dialect.areas }}
          </span>
          <span>
            <i
              class="fas fa-users"
              aria-hidden="true"
            />
            {{ dialect.speakers }}
          </span>
        </span>
      </button>
    </div>

    <div
      v-if="infoLoading"
      class="resources-state"
      role="status"
    >
      {{ currentName }}资料加载中…
    </div>
    <div
      v-else-if="infoError"
      class="resources-state resources-state-error"
      role="alert"
    >
      {{ infoError }}
      <button
        type="button"
        class="btn btn-outline btn-sm"
        @click="loadDialect(selectedDialect)"
      >
        重新加载
      </button>
    </div>
    <div
      v-else-if="info"
      class="dialect-detail"
    >
      <div class="dialect-greeting">
        <div class="greeting-main">
          {{ info.greeting }}
        </div>
        <div class="greeting-meaning">
          （{{ info.greeting_meaning }}）
        </div>
      </div>

      <div class="dialect-features">
        <span
          v-for="feature in info.features"
          :key="feature"
          class="feature-tag"
        >
          {{ feature }}
        </span>
      </div>

      <div
        v-if="info.phrases.length"
        class="phrases-panel"
      >
        <h4>
          <i
            class="fas fa-language"
            aria-hidden="true"
          />
          常用短语
        </h4>
        <div class="phrases-grid">
          <button
            v-for="phrase in info.phrases"
            :key="`${phrase.dialect}-${phrase.mandarin}`"
            type="button"
            class="phrase-item"
            :title="`点击提问：${phrase.dialect}`"
            @click="selectPhrase(phrase)"
          >
            <span class="phrase-dialect">{{ phrase.dialect }}</span>
            <span class="phrase-mandarin">{{ phrase.mandarin }}</span>
            <span class="phrase-pinyin">{{ phrase.pinyin }}</span>
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="info"
      class="voice-chat-area"
    >
      <div class="voice-chat-header">
        <h4>
          <i
            class="fas fa-comments"
            aria-hidden="true"
          />
          AI方言助手
        </h4>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          @click="clearChat"
        >
          <i
            class="fas fa-trash-alt"
            aria-hidden="true"
          />
          清空
        </button>
      </div>
      <div
        ref="messagesElement"
        class="voice-chat-messages"
        aria-live="polite"
      >
        <div
          v-if="!chat.length"
          class="voice-welcome"
        >
          <i
            class="fas fa-robot"
            aria-hidden="true"
          />
          <p>你好！我是方言农业助手，可以用普通话或方言向我提问</p>
        </div>
        <div
          v-for="entry in chat"
          :key="entry.id"
          class="voice-msg"
          :class="entry.role"
        >
          <template v-if="entry.role === 'bot'">
            <div
              v-if="entry.result"
              class="msg-dialect-tag"
            >
              {{ entry.result.dialect_name }}助手
            </div>
            <div class="voice-msg-body">
              {{ entry.text }}
            </div>
            <div
              v-if="entry.result"
              class="voice-msg-actions"
            >
              <button
                type="button"
                class="voice-speak-btn"
                :class="{
                  speaking:
                    speakingId === entry.id && ttsState === 'speaking',
                  paused: speakingId === entry.id && ttsState === 'paused',
                }"
                @click="speak(entry)"
              >
                <i
                  class="fas"
                  :class="
                    speakingId === entry.id && ttsState === 'speaking'
                      ? 'fa-pause'
                      : 'fa-volume-up'
                  "
                  aria-hidden="true"
                />
                {{
                  speakingId === entry.id && ttsState === "speaking"
                    ? "暂停"
                    : speakingId === entry.id && ttsState === "paused"
                      ? "继续"
                      : "朗读"
                }}
              </button>
              <span class="voice-msg-note">{{ sourceNote(entry) }}</span>
            </div>
            <div
              v-if="entry.result?.chem_notice"
              class="voice-msg-chem"
            >
              <i
                class="fas fa-exclamation-triangle"
                aria-hidden="true"
              />
              {{ entry.result.chem_notice }}
            </div>
            <div
              v-if="entry.result?.suggestions.length"
              class="msg-suggestions"
            >
              <button
                v-for="suggestion in entry.result.suggestions"
                :key="suggestion"
                type="button"
                class="suggestion-btn"
                @click="send(suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>
          </template>
          <template v-else>
            {{ entry.text }}
          </template>
        </div>
      </div>
      <div
        v-if="info.quick_questions.length"
        class="voice-quick-questions"
      >
        <button
          v-for="question in info.quick_questions"
          :key="question"
          type="button"
          class="voice-quick-btn"
          :disabled="sending"
          @click="send(question)"
        >
          {{ question }}
        </button>
      </div>
      <p
        v-if="voiceHint"
        class="voice-input-hint"
        role="status"
      >
        {{ voiceHint }}
      </p>
      <div class="voice-input-bar">
        <button
          type="button"
          class="voice-btn-small"
          :class="{ recording }"
          aria-label="语音输入"
          :aria-pressed="recording"
          @click="toggleRecording"
        >
          <i
            class="fas fa-microphone"
            aria-hidden="true"
          />
        </button>
        <input
          v-model="input"
          type="text"
          autocomplete="off"
          :placeholder="voiceHint || '输入你的问题...'"
          :disabled="sending"
          @keydown.enter.prevent="send()"
        >
        <button
          type="button"
          class="voice-send-btn"
          title="发送"
          :disabled="sending || !input.trim()"
          @click="send()"
        >
          <i
            class="fas fa-paper-plane"
            aria-hidden="true"
          />
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dialect-card,
.phrase-item {
  font: inherit;
  text-align: left;
}

.dialect-card {
  width: 100%;
  color: inherit;
}

.dialect-card-header > span:last-child {
  display: grid;
  gap: 2px;
}

.phrase-item {
  width: 100%;
}

.voice-input-hint {
  margin: 0;
  padding: 0 16px 10px;
  color: var(--accent-amber, #b7791f);
  font-size: 0.78rem;
}

.voice-msg-body {
  white-space: pre-wrap;
}

.msg-suggestions .suggestion-btn {
  font: inherit;
}

.resources-state {
  padding: 24px;
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  color: var(--text-secondary);
  text-align: center;
}

.resources-state-error {
  display: grid;
  justify-items: center;
  gap: 10px;
  color: var(--accent-amber, #b7791f);
}
</style>
