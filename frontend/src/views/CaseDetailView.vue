<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { getCases, type SuccessCase } from "@/api/resources";

type DetailState = "loading" | "ready" | "missing" | "error";

const route = useRoute();
const detail = ref<SuccessCase | null>(null);
const state = ref<DetailState>("loading");
const pendingCount = ref(0);
const sourceNote = ref("");
const lessonsNote = ref("");
const requestSequence = ref(0);

const numericId = computed(() => {
  const value = Number(route.params.id);
  return Number.isInteger(value) && value > 0 ? value : null;
});

watch(
  () => route.params.id,
  () => {
    void loadCase();
  },
);

onMounted(() => {
  void loadCase();
});

async function loadCase(): Promise<void> {
  const sequence = ++requestSequence.value;
  const caseId = numericId.value;
  detail.value = null;
  state.value = "loading";
  pendingCount.value = 0;
  sourceNote.value = "";
  lessonsNote.value = "";
  if (!caseId) {
    state.value = "missing";
    return;
  }

  try {
    const list = await getCases();
    if (sequence !== requestSequence.value) return;
    const item = list.cases.find((candidate) => candidate.id === caseId);
    pendingCount.value = list.case_review.pending;
    if (!item) {
      state.value = "missing";
      return;
    }
    detail.value = item;
    sourceNote.value = list.source_note;
    lessonsNote.value = list.lessons_note;
    state.value = "ready";
  } catch {
    if (sequence !== requestSequence.value) return;
    state.value = "error";
  }
}

function paragraphs(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function safeUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : "";
}
</script>

<template>
  <section class="case-detail-view">
    <div
      v-if="state === 'loading'"
      class="loading-state"
      role="status"
    >
      <div class="spinner-lg" />
      <p>正在加载案例详情...</p>
    </div>

    <div
      v-else-if="state === 'missing'"
      class="error-state"
      role="alert"
    >
      <i
        class="fas fa-exclamation-circle"
        aria-hidden="true"
      />
      <h1>案例未找到</h1>
      <p>
        未找到 ID 为 {{ numericId ?? "未知" }} 的案例：它可能尚未通过超级管理员审核<span
          v-if="pendingCount"
        >（当前待审 {{ pendingCount }} 条）</span>，或链接已失效。
      </p>
      <RouterLink
        class="btn btn-primary"
        to="/resources"
      >
        <i
          class="fas fa-arrow-left"
          aria-hidden="true"
        />
        返回资源库
      </RouterLink>
    </div>

    <div
      v-else-if="state === 'error'"
      class="error-state"
      role="alert"
    >
      <i
        class="fas fa-exclamation-circle"
        aria-hidden="true"
      />
      <h1>加载失败</h1>
      <p>无法连接服务器，请稍后重试。</p>
      <button
        type="button"
        class="btn btn-primary"
        @click="loadCase"
      >
        <i
          class="fas fa-redo"
          aria-hidden="true"
        />
        重试
      </button>
    </div>

    <template v-else-if="detail">
      <header class="case-hero">
        <div class="location-tag">
          <i
            class="fas fa-map-marker-alt"
            aria-hidden="true"
          />
          {{ detail.location }}
        </div>
        <h1>{{ detail.title }}</h1>
        <p class="subtitle">
          {{ detail.description }}
        </p>
      </header>

      <div
        v-if="detail.stats.length"
        class="stats-grid"
      >
        <div
          v-for="stat in detail.stats"
          :key="`${stat.label}-${stat.value}`"
          class="stat-detail-card"
        >
          <div class="stat-icon">
            <i
              class="fas"
              :class="stat.icon || 'fa-chart-line'"
              aria-hidden="true"
            />
          </div>
          <div class="stat-value">
            {{ stat.value }}
          </div>
          <div class="stat-label">
            {{ stat.label }}
          </div>
        </div>
      </div>

      <section class="content-card">
        <h2>
          <i
            class="fas fa-info-circle"
            aria-hidden="true"
          />
          案例背景
        </h2>
        <div class="prose">
          <p
            v-for="(paragraph, index) in paragraphs(detail.background)"
            :key="index"
          >
            {{ paragraph }}
          </p>
        </div>
      </section>

      <section
        v-if="detail.milestones.length"
        class="content-card"
      >
        <h2>
          <i
            class="fas fa-route"
            aria-hidden="true"
          />
          关键节点
        </h2>
        <div class="timeline">
          <article
            v-for="milestone in detail.milestones"
            :key="`${milestone.period}-${milestone.title}`"
            class="timeline-item"
          >
            <div
              v-if="milestone.period"
              class="t-period"
            >
              {{ milestone.period }}
            </div>
            <div class="t-title">
              {{ milestone.title }}
            </div>
            <div class="t-desc">
              {{ milestone.desc }}
            </div>
          </article>
        </div>
      </section>

      <blockquote
        v-if="detail.quote && detail.quote_author"
        class="quote-block"
      >
        <p>{{ detail.quote }}</p>
        <div class="quote-author">
          —— {{ detail.quote_author }}
        </div>
      </blockquote>

      <section
        v-if="detail.lessons.length"
        class="content-card"
      >
        <h2>
          <i
            class="fas fa-lightbulb"
            aria-hidden="true"
          />
          借鉴与启示
        </h2>
        <p
          v-if="lessonsNote"
          class="section-note"
        >
          {{ lessonsNote }}
        </p>
        <ul>
          <li
            v-for="lesson in detail.lessons"
            :key="lesson"
          >
            {{ lesson }}
          </li>
        </ul>
      </section>

      <section
        v-if="detail.sources.length"
        class="content-card case-sources"
      >
        <h2>
          <i
            class="fas fa-book-open"
            aria-hidden="true"
          />
          资料来源
        </h2>
        <p
          v-if="sourceNote"
          class="section-note"
        >
          {{ sourceNote }}
        </p>
        <ul>
          <li
            v-for="source in detail.sources"
            :key="`${source.title}-${source.url}`"
          >
            <a
              v-if="safeUrl(source.url)"
              :href="safeUrl(source.url)"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ source.title }}
            </a>
            <span v-else>{{ source.title }}</span>
            <span class="src-meta">
              {{ source.media }}{{ source.date ? ` · ${source.date}` : "" }}
            </span>
          </li>
        </ul>
      </section>

      <div class="case-detail-actions">
        <RouterLink
          class="btn btn-primary"
          to="/resources"
        >
          <i
            class="fas fa-arrow-left"
            aria-hidden="true"
          />
          返回资源库
        </RouterLink>
      </div>
    </template>
  </section>
</template>

<style scoped>
.case-detail-view {
  width: min(960px, calc(100% - 48px));
  margin: 0 auto;
  padding: 48px 0 72px;
}

.case-hero {
  position: relative;
  overflow: hidden;
  margin-bottom: 28px;
  padding: 48px 40px;
  border-radius: var(--radius);
  background: var(--gradient-main);
  color: #fff;
}

.case-hero::after {
  position: absolute;
  top: -40%;
  right: -10%;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  content: "";
}

.location-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  padding: 5px 14px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.18);
  font-size: 0.85rem;
}

.case-hero h1 {
  position: relative;
  z-index: 1;
  margin: 0 0 10px;
  font-size: 1.8rem;
  font-weight: 500;
}

.case-hero .subtitle {
  position: relative;
  z-index: 1;
  max-width: 520px;
  margin: 0;
  font-size: 1rem;
  line-height: 1.6;
  opacity: 0.9;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}

.stat-detail-card {
  padding: 24px 20px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  box-shadow: var(--shadow-sm);
  text-align: center;
}

.stat-detail-card .stat-icon {
  display: flex;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--gradient-main);
  color: #fff;
  font-size: 1.1rem;
}

.stat-detail-card .stat-value {
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-detail-card .stat-label {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.content-card {
  margin-bottom: 28px;
  padding: 32px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  background: var(--bg-secondary);
  box-shadow: var(--shadow-sm);
}

.content-card h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  font-size: 1.2rem;
  font-weight: 600;
}

.content-card h2 i {
  color: var(--accent-blue);
}

.content-card p,
.content-card li {
  color: var(--text-secondary);
  font-size: 0.95rem;
  line-height: 1.8;
}

.content-card ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.content-card ul li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}

.content-card ul li:last-child {
  border-bottom: 0;
}

.content-card ul li::before {
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--accent-green);
  content: "";
}

.prose p + p {
  margin-top: 12px;
}

.timeline {
  position: relative;
  padding-left: 28px;
}

.timeline::before {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 8px;
  width: 2px;
  background: var(--border);
  content: "";
}

.timeline-item {
  position: relative;
  margin-bottom: 20px;
}

.timeline-item::before {
  position: absolute;
  top: 6px;
  left: -24px;
  width: 12px;
  height: 12px;
  border: 2px solid var(--bg-secondary);
  border-radius: 50%;
  background: var(--accent-blue);
  box-shadow: 0 0 0 2px var(--accent-blue);
  content: "";
}

.t-period {
  display: inline-block;
  margin-bottom: 6px;
  padding: 2px 10px;
  border-radius: 9999px;
  background: rgba(0, 180, 216, 0.12);
  color: var(--accent-blue);
  font-size: 0.72rem;
  font-weight: 600;
}

.t-title {
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 600;
}

.t-desc {
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.6;
}

.quote-block {
  margin: 0 0 28px;
  padding: 20px 24px;
  border-left: 4px solid var(--accent-blue);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
  background: linear-gradient(
    135deg,
    rgba(0, 180, 216, 0.06),
    rgba(16, 185, 129, 0.06)
  );
}

.quote-block p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
  font-style: italic;
  line-height: 1.7;
}

.quote-author {
  margin-top: 10px;
  color: var(--accent-blue);
  font-size: 0.85rem;
  font-weight: 600;
}

.section-note {
  margin: -6px 0 14px;
  color: var(--text-muted);
  font-size: 0.8rem;
  line-height: 1.6;
}

.case-sources li {
  display: block;
  padding: 12px 0;
}

.case-sources li::before {
  display: none;
}

.case-sources a {
  color: var(--accent-blue);
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.5;
  text-decoration: none;
  overflow-wrap: anywhere;
}

.case-sources a:hover {
  text-decoration: underline;
}

.src-meta {
  display: block;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.case-detail-actions {
  display: flex;
  justify-content: center;
}

.loading-state,
.error-state {
  padding: 80px 20px;
  text-align: center;
}

.loading-state p,
.error-state p {
  color: var(--text-muted);
}

.error-state h1 {
  margin-bottom: 8px;
  font-size: 1.2rem;
}

.spinner-lg {
  width: 48px;
  height: 48px;
  margin: 0 auto 20px;
  border: 4px solid var(--border);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
