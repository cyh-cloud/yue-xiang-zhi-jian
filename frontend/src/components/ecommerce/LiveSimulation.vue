<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import {
  analyzeLiveReading,
  generateLiveComments,
  type LiveReadingReport,
} from "@/api/ecommerce";
import { describeApiError } from "@/shared/apiErrors";

const props = defineProps<{
  product: string;
  script: string;
}>();

const emit = defineEmits<{
  report: [report: LiveReadingReport | null, script: string];
}>();

type Difficulty = "新手" | "进阶" | "挑战";

interface LiveComment {
  id: number;
  user: string;
  text: string;
}

interface SpeechResult {
  isFinal: boolean;
  [index: number]: { transcript: string };
}

interface SpeechResultList {
  length: number;
  [index: number]: SpeechResult;
}

interface SpeechResultEvent {
  resultIndex: number;
  results: SpeechResultList;
}

interface SpeechErrorEvent {
  error: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

const SPEECH_USERS = [
  "小明",
  "阿花",
  "老王",
  "靓妹",
  "农家大姐",
  "吃货小李",
  "广东阿叔",
  "深圳打工仔",
  "佛山靓女",
  "潮汕老板",
];

const PRODUCT_COMMENTS: Record<string, string[]> = {
  荔枝: ["这个荔枝甜不甜？", "多少钱一箱？", "广东哪里的？", "包邮吗？"],
  龙眼: ["龙眼甜吗？", "肉厚不厚？", "哪里产的？", "几斤装？"],
  柑橘: ["是砂糖橘还是沃柑？", "甜不甜？", "几斤装？", "有优惠吗？"],
  香蕉: ["什么品种？", "香不香？", "怎么保存？", "有优惠吗？"],
  水产养殖: ["鱼新鲜吗？", "怎么配送？", "什么品种？", "几斤起卖？"],
  水稻: ["什么品种？", "多少钱一斤？", "新米吗？", "产地哪里？"],
  茶叶: ["什么茶？", "多少钱一斤？", "春茶还是秋茶？", "有礼盒装吗？"],
  蔬菜: ["有机的吗？", "怎么配送？", "新鲜吗？", "几斤起送？"],
};

const HARD_COMMENTS = [
  "别家更便宜，凭什么买你的？",
  "有农残检测报告吗？口说无凭",
  "包邮吗？不包邮就算了",
  "支持退货吗？坏了怎么办？",
];

const REACTIONS = [
  {
    pattern: /扣\s*\d|扣一|点个赞|点赞|关注|想要的|评论区|公屏/,
    label: "互动指令",
    likes: 6,
    comment: true,
  },
  {
    pattern: /价|元|块|钱|优惠|折扣|包邮|特价|划算/,
    label: "价格信息",
    likes: 3,
    comment: true,
  },
  {
    pattern: /斤|克|公斤|规格|果径|个头|品相|箱|装|份|袋/,
    label: "规格说明",
    likes: 2,
    comment: true,
  },
  {
    pattern: /甜|香|鲜|脆|嫩|糯|口感|风味|好吃|汁水/,
    label: "口感卖点",
    likes: 3,
    comment: true,
  },
  {
    pattern: /广东|岭南|产地|原产|种植|养殖|果园|农场|产区/,
    label: "产地卖点",
    likes: 2,
    comment: true,
  },
  {
    pattern: /售后|退|换|赔|保障|包退|包赔|放心|时效/,
    label: "售后保障",
    likes: 2,
    comment: true,
  },
];

const running = ref(false);
const difficulty = ref<Difficulty>("新手");
const seconds = ref(0);
const viewers = ref(0);
const likes = ref(0);
const commentCount = ref(0);
const comments = ref<LiveComment[]>([]);
const sessionFeedback = ref<string[]>([]);
const readingRunning = ref(false);
const readingSeconds = ref(0);
const transcript = ref("");
const interim = ref("");
const maxSilenceSec = ref(0);
const micStatus = ref("点「开始朗读」，对着麦克风念你的话术");
const micHint = ref("需要麦克风权限；浏览器不支持语音识别时可只用文本练习");
const report = ref<LiveReadingReport | null>(null);
const reportedScript = ref("");
const analyzing = ref(false);
const readingError = ref("");
const aiNotice = ref("");

let simulationTimer: ReturnType<typeof setInterval> | null = null;
let introTimer: ReturnType<typeof setInterval> | null = null;
let ambientCommentTimer: ReturnType<typeof setInterval> | null = null;
let readingTimer: ReturnType<typeof setInterval> | null = null;
let recognition: SpeechRecognitionLike | null = null;
let nextCommentId = 1;
let speaking = false;
let silenceSec = 0;
let lastResultAt = 0;
let lastAiCommentAt = 0;
let readingStartedAt = 0;

const speechConstructor = computed<SpeechRecognitionConstructor | null>(() => {
  const speechWindow = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return speechWindow.SpeechRecognition
    ?? speechWindow.webkitSpeechRecognition
    ?? null;
});

const durationLabel = computed(() => formatClock(seconds.value));
const readingDurationLabel = computed(() => formatClock(readingSeconds.value));
const transcriptText = computed(
  () => `${transcript.value}${interim.value}`.trim()
    || "（开始朗读后显示识别到的内容）",
);
const reportIsStale = computed(
  () => Boolean(report.value && reportedScript.value !== props.script.trim()),
);

function formatClock(totalSeconds: number): string {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const remainder = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function randomItem<T>(items: readonly T[]): T {
  return items[Math.floor(Math.random() * items.length)]!;
}

function commentPool(): string[] {
  return PRODUCT_COMMENTS[props.product] ?? PRODUCT_COMMENTS.荔枝!;
}

function addComment(user: string, text: string, counted = true): void {
  comments.value.push({
    id: nextCommentId++,
    user,
    text,
  });
  if (comments.value.length > 30) comments.value.shift();
  if (counted) commentCount.value += 1;
}

function addSessionFeedback(message: string): void {
  sessionFeedback.value = [
    message,
    ...sessionFeedback.value.filter((item) => item !== message),
  ].slice(0, 5);
}

function addAudienceComment(): void {
  const hardRatio = difficulty.value === "挑战"
    ? 0.6
    : difficulty.value === "进阶"
      ? 0.35
      : 0;
  const text = Math.random() < hardRatio
    ? randomItem(HARD_COMMENTS)
    : randomItem(commentPool());
  addComment(randomItem(SPEECH_USERS), text);
}

function clearSimulationTimers(): void {
  if (simulationTimer) clearInterval(simulationTimer);
  if (introTimer) clearInterval(introTimer);
  if (ambientCommentTimer) clearInterval(ambientCommentTimer);
  simulationTimer = null;
  introTimer = null;
  ambientCommentTimer = null;
}

function startSimulation(): void {
  if (running.value) return;
  running.value = true;
  seconds.value = 0;
  viewers.value = 5;
  likes.value = 0;
  commentCount.value = 0;
  comments.value = [];
  sessionFeedback.value = [];
  silenceSec = 0;
  maxSilenceSec.value = 0;
  speaking = false;
  lastAiCommentAt = 0;
  aiNotice.value = "";
  addComment("系统", "直播间已开启，等待观众进入...", false);
  addSessionFeedback("直播已开始，先说清产品与欢迎语。");

  simulationTimer = setInterval(() => {
    seconds.value += 1;
    if (readingRunning.value && !speaking) {
      silenceSec += 1;
      maxSilenceSec.value = Math.max(maxSilenceSec.value, silenceSec);
      if (silenceSec > 0 && silenceSec % 5 === 0) {
        viewers.value = Math.max(0, viewers.value - 2);
        addSessionFeedback("连续冷场，观众正在离开，尽快补上互动或卖点。");
      }
    } else if (speaking) {
      silenceSec = 0;
    }
  }, 1000);

  let entered = 0;
  introTimer = setInterval(() => {
    entered += 1;
    viewers.value += Math.floor(Math.random() * 4) + 1;
    if (entered >= 4 && introTimer) {
      clearInterval(introTimer);
      introTimer = null;
    }
  }, 1500);

  ambientCommentTimer = setInterval(() => {
    if (!running.value) return;
    addAudienceComment();
    addSessionFeedback("观众持续提问，注意逐条回应公屏问题。");
  }, 8000);
}

function stopSimulation(): void {
  running.value = false;
  clearSimulationTimers();
  stopReading();
}

function reactToSpeech(text: string): void {
  const matched = REACTIONS.filter((reaction) => reaction.pattern.test(text));
  if (!matched.length) {
    addSessionFeedback("这段话没有命中明显卖点，补上产地、规格、价格或售后信息。");
    return;
  }

  let gainedLikes = 0;
  matched.forEach((reaction) => {
    gainedLikes += reaction.likes;
    addSessionFeedback(`命中${reaction.label}，现场点赞 +${reaction.likes}。`);
    if (reaction.comment) addAudienceComment();
  });
  likes.value += gainedLikes;
  viewers.value += Math.floor(matched.length / 2) + 1;
}

async function maybeAskAiAudience(text: string): Promise<void> {
  if (!running.value || !text.trim()) return;
  if (Date.now() - lastAiCommentAt < 12_000) return;
  lastAiCommentAt = Date.now();
  try {
    const response = await generateLiveComments({
      speech: (transcript.value || text).slice(0, 200),
      product: props.product,
      difficulty: difficulty.value,
    });
    response.comments.forEach((comment) => {
      addComment(randomItem(SPEECH_USERS), comment);
    });
    aiNotice.value = "AI 观众已根据刚才的话术追加提问。";
  } catch {
    aiNotice.value = "AI 观众暂不可用，已使用规则评论继续训练。";
  }
}

function handleSpeech(text: string): void {
  reactToSpeech(text);
  void maybeAskAiAudience(text);
}

function startReading(): void {
  if (readingRunning.value) return;
  if (!speechConstructor.value) {
    micStatus.value = "当前浏览器不支持语音识别";
    micHint.value = "建议使用 Chrome 或 Edge；仍可用文本方式练习并提交话术。";
    return;
  }

  startSimulation();
  transcript.value = "";
  interim.value = "";
  readingSeconds.value = 0;
  readingStartedAt = Date.now();
  maxSilenceSec.value = 0;
  readingError.value = "";
  report.value = null;
  reportedScript.value = "";
  emit("report", null, "");
  readingRunning.value = true;

  const rec = new speechConstructor.value();
  rec.lang = "zh-CN";
  rec.continuous = true;
  rec.interimResults = true;
  rec.onstart = () => {
    micStatus.value = "正在聆听，请对着麦克风念你的话术";
    micHint.value = "识别有延迟，属正常现象";
  };
  rec.onresult = (event) => {
    let pending = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index]!;
      const text = result[0]?.transcript ?? "";
      if (result.isFinal) {
        transcript.value += text;
        handleSpeech(text);
      } else {
        pending += text;
      }
    }
    interim.value = pending;
    lastResultAt = Date.now();
    speaking = true;
    silenceSec = 0;
  };
  rec.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      micStatus.value = "麦克风权限被拒绝";
      micHint.value = "请在浏览器地址栏允许麦克风后重试。";
    } else if (event.error !== "no-speech" && event.error !== "aborted") {
      micStatus.value = `语音识别中断：${event.error}`;
      micHint.value = "可点「结束朗读」后重新开始。";
    }
  };
  rec.onend = () => {
    if (readingRunning.value) {
      try {
        rec.start();
      } catch {
        // The browser may still consider the previous session active.
      }
    }
  };

  try {
    rec.start();
  } catch {
    readingRunning.value = false;
    micStatus.value = "无法启动语音识别";
    micHint.value = "请检查浏览器权限，或改用文本方式练习。";
    return;
  }
  recognition = rec;

  readingTimer = setInterval(() => {
    readingSeconds.value += 1;
    if (lastResultAt && Date.now() - lastResultAt > 2500) {
      speaking = false;
    }
  }, 1000);
}

function stopReading(): void {
  readingRunning.value = false;
  if (readingTimer) clearInterval(readingTimer);
  readingTimer = null;
  try {
    recognition?.stop();
  } catch {
    // Stopping an already closed recognition session is harmless.
  }
  recognition = null;
  speaking = false;
  silenceSec = 0;
  if (transcript.value.trim()) {
    micStatus.value = "朗读已结束";
    micHint.value = "可点「分析朗读」查看完成度、语速与必卖点命中。";
  }
}

async function analyzeReading(): Promise<void> {
  readingError.value = "";
  if (!props.script.trim()) {
    readingError.value = "请先写出「我的稿」再分析朗读。";
    return;
  }
  if (!transcript.value.trim()) {
    readingError.value = "还没有识别到朗读内容，请先点「开始朗读」。";
    return;
  }

  const analyzedScript = props.script.trim();
  analyzing.value = true;
  try {
    const response = await analyzeLiveReading({
      script: analyzedScript,
      transcript: transcript.value.trim(),
      duration_sec: Math.max(
        1,
        Math.round((Date.now() - readingStartedAt) / 1000),
      ),
      max_silence_sec: maxSilenceSec.value,
    });
    report.value = response.report;
    reportedScript.value = analyzedScript;
    emit("report", response.report, analyzedScript);
  } catch (error) {
    report.value = null;
    reportedScript.value = "";
    emit("report", null, "");
    readingError.value = describeApiError(
      error,
      "分析失败，请稍后重试。",
    );
  } finally {
    analyzing.value = false;
  }
}

watch(
  () => props.product,
  () => {
    comments.value = [];
    commentCount.value = 0;
    sessionFeedback.value = [];
    aiNotice.value = "";
  },
);

onBeforeUnmount(() => {
  stopSimulation();
});
</script>

<template>
  <section
    id="live-simulation"
    class="live-simulation"
    data-testid="live-simulation"
    aria-labelledby="live-simulation-title"
  >
    <div class="simulation-header">
      <div>
        <h4 id="live-simulation-title">
          <i
            class="fas fa-broadcast-tower"
            aria-hidden="true"
          />
          直播模拟训练
        </h4>
        <p>朗读「我的稿」，观众评论和现场指标会随你的表现变化。</p>
      </div>
      <span
        class="live-badge"
        :class="{ active: running }"
        data-testid="live-badge"
      >
        <i
          class="fas fa-circle"
          aria-hidden="true"
        />
        {{ running ? "模拟直播中" : "直播未开始" }}
      </span>
    </div>

    <div class="simulation-grid">
      <div class="live-stage">
        <div class="cam-product-tag">
          <i
            class="fas fa-apple-alt"
            aria-hidden="true"
          />
          {{ product }}
        </div>
        <div class="mic-overlay">
          <i
            class="fas"
            :class="readingRunning ? 'fa-microphone-lines' : 'fa-microphone'"
            aria-hidden="true"
          />
          <p>{{ micStatus }}</p>
          <span>{{ micHint }}</span>
        </div>

        <div class="reader-bar">
          <button
            v-if="!running"
            type="button"
            class="btn btn-primary btn-sm"
            @click="startSimulation"
          >
            <i
              class="fas fa-video"
              aria-hidden="true"
            />
            开始直播
          </button>
          <button
            v-else
            type="button"
            class="btn btn-outline btn-sm"
            @click="stopSimulation"
          >
            <i
              class="fas fa-stop"
              aria-hidden="true"
            />
            结束直播
          </button>
          <button
            v-if="!readingRunning"
            type="button"
            class="btn btn-primary btn-sm"
            @click="startReading"
          >
            <i
              class="fas fa-microphone"
              aria-hidden="true"
            />
            开始朗读
          </button>
          <button
            v-else
            type="button"
            class="btn btn-outline btn-sm"
            @click="stopReading"
          >
            <i
              class="fas fa-stop"
              aria-hidden="true"
            />
            结束朗读
          </button>
          <span class="reader-timer">{{ readingDurationLabel }}</span>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="analyzing"
            @click="analyzeReading"
          >
            <i
              class="fas"
              :class="analyzing ? 'fa-spinner fa-spin' : 'fa-wave-square'"
              aria-hidden="true"
            />
            {{ analyzing ? "分析中..." : "分析朗读" }}
          </button>
        </div>

        <div
          class="live-transcript"
          data-testid="live-transcript"
        >
          <span class="transcript-label">实时识别</span>
          <p>{{ transcriptText }}</p>
        </div>

        <div class="live-stats">
          <span>
            <i
              class="fas fa-eye"
              aria-hidden="true"
            />
            <strong>{{ viewers }}</strong> 观众
          </span>
          <span>
            <i
              class="fas fa-heart"
              aria-hidden="true"
            />
            <strong>{{ likes }}</strong> 点赞
          </span>
          <span>
            <i
              class="fas fa-comment"
              aria-hidden="true"
            />
            <strong data-testid="live-comment-count">{{ commentCount }}</strong> 评论
          </span>
          <span>
            <i
              class="fas fa-clock"
              aria-hidden="true"
            />
            <strong>{{ durationLabel }}</strong>
          </span>
        </div>

        <div
          class="live-comments"
          data-testid="live-comments"
        >
          <div
            v-for="comment in comments"
            :key="comment.id"
            class="comment-item"
          >
            <span class="comment-user">{{ comment.user }}：</span>{{ comment.text }}
          </div>
        </div>
      </div>

      <div class="simulation-feedback">
        <div class="simulation-controls">
          <label for="live-difficulty">训练难度</label>
          <select
            id="live-difficulty"
            v-model="difficulty"
            :disabled="running"
          >
            <option value="新手">
              新手 · 观众友善
            </option>
            <option value="进阶">
              进阶 · 会质疑比价
            </option>
            <option value="挑战">
              挑战 · 有突发状况
            </option>
          </select>
        </div>

        <div class="session-feedback">
          <h5>
            <i
              class="fas fa-lightbulb"
              aria-hidden="true"
            />
            现场反馈
          </h5>
          <ul data-testid="live-session-feedback">
            <li
              v-for="item in sessionFeedback"
              :key="item"
            >
              {{ item }}
            </li>
          </ul>
          <p
            v-if="!sessionFeedback.length"
            class="simulation-empty"
          >
            开始朗读后，这里会显示互动、卖点和冷场反馈。
          </p>
          <p
            v-if="aiNotice"
            class="ai-notice"
          >
            {{ aiNotice }}
          </p>
        </div>

        <div class="reading-report">
          <div class="reading-report-head">
            <h5>
              <i
                class="fas fa-wave-square"
                aria-hidden="true"
              />
              朗读实录分析
            </h5>
            <span>规则分析 · 可复现</span>
          </div>

          <p
            v-if="readingError"
            class="reading-error"
            data-testid="reading-error"
            role="alert"
          >
            {{ readingError }}
          </p>

          <div
            v-if="report"
            class="reading-body"
          >
            <div
              class="reading-overall"
              data-testid="reading-overall"
            >
              {{ report.overall_score }}
            </div>
            <div
              class="reading-metrics"
              data-testid="reading-metrics"
            >
              <div class="reading-metric">
                <label>稿子完成度</label>
                <strong>{{ report.coverage }}%</strong>
              </div>
              <div class="reading-metric">
                <label>真实语速</label>
                <strong>{{ report.speed_cpm }} 字/分</strong>
              </div>
              <div class="reading-metric">
                <label>必卖点命中</label>
                <strong>{{ report.rubric_hit }}/{{ report.rubric_total }}</strong>
              </div>
              <div class="reading-metric">
                <label>最长冷场</label>
                <strong>{{ report.max_silence_sec }} 秒</strong>
              </div>
            </div>
            <div class="reading-rubric">
              <span
                v-for="item in report.rubric_items"
                :key="item.name"
                class="rubric-chip"
                :class="item.said ? 'hit' : item.in_script ? 'missed' : 'absent'"
              >
                {{ item.name }}
                <em>{{ item.said ? "已说出" : item.in_script ? "稿里有、没说" : "稿里也缺" }}</em>
              </span>
            </div>
            <div class="reading-tips">
              <p
                v-for="tip in report.tips"
                :key="tip"
              >
                <i
                  class="fas fa-lightbulb"
                  aria-hidden="true"
                />
                {{ tip }}
              </p>
              <p v-if="!report.tips.length">
                <i
                  class="fas fa-check"
                  aria-hidden="true"
                />
                没发现明显问题
              </p>
            </div>
            <p
              v-if="reportIsStale"
              class="report-stale"
            >
              「我的稿」已改动，这份朗读报告不会随本次提交保存。
            </p>
          </div>
          <p
            v-else-if="!readingError"
            class="simulation-empty"
          >
            念一遍你自己的稿子，这里会给出完成度、真实语速与必卖点命中情况。
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.live-simulation {
  margin-bottom: 24px;
  padding: 20px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
}

.simulation-header,
.reading-report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.simulation-header {
  margin-bottom: 16px;
}

.simulation-header h4,
.reading-report-head h5 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--text-primary);
}

.simulation-header h4 {
  font-size: 1rem;
}

.simulation-header h4 i,
.reading-report-head h5 i {
  color: var(--accent-blue);
}

.simulation-header p {
  margin: 5px 0 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.simulation-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 16px;
}

.live-stage {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.mic-overlay {
  display: flex;
  min-height: 112px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 28px 0 12px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  text-align: center;
}

.mic-overlay i {
  margin-bottom: 7px;
  font-size: 1.8rem;
}

.mic-overlay p {
  margin: 0 0 4px;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.mic-overlay span {
  padding: 0 14px;
  font-size: 0.7rem;
  line-height: 1.5;
}

.reader-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.reader-timer {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
}

.live-transcript {
  min-height: 36px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-xs);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.55;
}

.transcript-label {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 7px;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  color: var(--accent-blue);
  font-size: 0.65rem;
}

.live-transcript p {
  display: inline;
  margin: 0;
}

.live-comments {
  min-height: 100px;
  max-height: 150px;
}

.simulation-feedback {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}

.simulation-controls,
.session-feedback,
.reading-report {
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.simulation-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.simulation-controls label {
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 600;
}

.simulation-controls select {
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font: inherit;
  font-size: 0.75rem;
}

.session-feedback h5,
.reading-report-head h5 {
  margin: 0;
  font-size: 0.85rem;
}

.session-feedback ul {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 10px 0 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
}

.ai-notice {
  margin: 10px 0 0;
  color: var(--text-muted);
  font-size: 0.72rem;
}

.reading-report-head {
  margin-bottom: 10px;
}

.reading-report-head > span {
  color: var(--text-muted);
  font-size: 0.68rem;
}

.reading-error {
  margin: 0;
  color: #b3382f;
  font-size: 0.78rem;
  line-height: 1.5;
}

.reading-overall {
  margin: 0 auto 12px;
  color: var(--accent-blue);
  font-size: 2rem;
  font-weight: 700;
  text-align: center;
}

.reading-metrics {
  display: flex;
  flex-direction: column;
}

.reading-metric {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-light);
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.reading-metric strong {
  color: var(--text-primary);
}

.reading-rubric {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.rubric-chip {
  display: inline-flex;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 0.68rem;
}

.rubric-chip em {
  opacity: 0.65;
  font-style: normal;
}

.rubric-chip.hit {
  border-color: rgba(31, 94, 67, 0.3);
  background: rgba(31, 94, 67, 0.06);
}

.rubric-chip.missed {
  border-color: rgba(217, 162, 39, 0.35);
  background: rgba(217, 162, 39, 0.07);
}

.rubric-chip.absent {
  opacity: 0.6;
}

.reading-tips {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 12px;
}

.reading-tips p {
  display: flex;
  gap: 6px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.5;
}

.reading-tips i {
  margin-top: 3px;
  color: #d9a227;
  font-size: 0.65rem;
}

.report-stale {
  margin: 10px 0 0;
  color: #a36d00;
  font-size: 0.72rem;
}

.simulation-empty {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 0.76rem;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .simulation-grid {
    grid-template-columns: 1fr;
  }
}
</style>
