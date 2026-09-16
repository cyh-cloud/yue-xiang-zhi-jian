<script setup lang="ts">
import {
  Check,
  History,
  LoaderCircle,
  Mic2,
  RotateCcw,
  Sparkles
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useEcommerceSimulationStore } from '@/stores/ecommerceSimulation'

const store = useEcommerceSimulationStore()
const auth = useAuthStore()
const router = useRouter()

const dimensionLabels = {
  pacing: '语速节奏',
  emotion: '情绪感染力',
  interaction: '互动引导',
  selling_point: '卖点突出'
} as const

const dimensions = [
  'pacing',
  'emotion',
  'interaction',
  'selling_point'
] as const

const activeSceneLabel = computed(
  () => store.current?.scene_label ?? ''
)

const scoreActionLabel = computed(() => {
  if (store.scoring) {
    return '评分中...'
  }
  if (store.current?.status === 'completed') {
    return '已完成评分'
  }
  return store.error === 'AI 服务暂时不可用' ? '重试评分' : '提交评分'
})

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
}

function isSegmentSaved(segmentKey: string): boolean {
  return store.savedSegments[segmentKey] === true
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void Promise.all([store.loadScenes(), store.loadHistory()])
})
</script>

<template>
  <div class="simulation-page">
    <AppHeader
      source="live"
      :loading="store.isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="simulation-shell">
      <header class="page-heading">
        <p class="page-kicker">04 / 电商运营实训</p>
        <h1>文字直播间模拟训练</h1>
        <p>
          每次选择一个直播场景，按固定顺序完成全部文字环节，再提交整场四维评分。
        </p>
      </header>

      <div class="workspace">
        <aside class="panel scene-panel" aria-labelledby="scene-title">
          <div class="panel-heading">
            <Mic2 :size="18" aria-hidden="true" />
            <h2 id="scene-title">选择场景</h2>
          </div>
          <ul>
            <li
              v-for="scene in store.scenes"
              :key="scene.key"
              data-test="simulation-scene-option"
            >
              <button
                type="button"
                :data-test="`simulation-scene-${scene.key}`"
                :class="{ 'is-active': store.current?.scene_key === scene.key }"
                :disabled="store.isBusy"
                @click="store.start(scene.key)"
              >
                <span>{{ scene.label }}</span>
                <small>{{ scene.segments.length }} 个环节</small>
              </button>
            </li>
          </ul>
        </aside>

        <section class="panel training-panel" aria-labelledby="training-title">
          <div class="panel-heading">
            <Sparkles :size="18" aria-hidden="true" />
            <h2 id="training-title">训练内容</h2>
            <span v-if="store.current">
              {{ store.current.status === 'completed' ? '已评分' : '进行中' }}
            </span>
          </div>

          <div
            v-if="store.current"
            data-test="simulation-active-scene"
            class="active-scene"
          >
            <header class="scene-heading">
              <div>
                <p>当前场景</p>
                <h2>{{ activeSceneLabel }}</h2>
              </div>
              <time :datetime="store.current.created_at">
                {{ formatTime(store.current.created_at) }}
              </time>
            </header>

            <div class="segment-list">
              <div
                v-for="segment in store.current.segments"
                :key="segment.key"
                data-test="simulation-segment"
              >
                <article
                  :data-test="`simulation-segment-${segment.key}`"
                  class="segment-card"
                >
                  <div class="segment-heading">
                    <h3>{{ segment.label }}</h3>
                    <span v-if="isSegmentSaved(segment.key)" class="saved-mark">
                      <Check :size="14" aria-hidden="true" />
                      已保存
                    </span>
                  </div>
                  <textarea
                    v-model="store.drafts[segment.key]"
                    rows="4"
                    :disabled="
                      isSegmentSaved(segment.key) ||
                      store.current.status === 'completed'
                    "
                    :aria-label="`${segment.label}文字话术`"
                    placeholder="输入本环节的直播话术"
                  />
                  <div class="segment-actions">
                    <button
                      type="button"
                      :data-test="`simulation-save-${segment.key}`"
                      :disabled="
                      isSegmentSaved(segment.key) ||
                      !store.drafts[segment.key]?.trim() ||
                      store.current.status === 'completed' ||
                      store.isBusy
                    "
                      @click="store.saveSegment(segment.key, store.drafts[segment.key] ?? '')"
                    >
                      {{ isSegmentSaved(segment.key) ? '已保存' : '保存环节' }}
                    </button>
                  </div>
                </article>
              </div>
            </div>

            <p
              v-if="store.error"
              class="error-message"
              role="alert"
              aria-live="assertive"
            >
              {{ store.error }}
            </p>

            <div class="score-action">
              <div>
                <strong>整场统一评分</strong>
                <p>全部环节保存后，由 AI 对整次训练进行四维评分。</p>
              </div>
              <button
                type="button"
                data-test="simulation-score"
                :disabled="!store.canScore || store.isBusy"
                @click="store.score()"
              >
                <LoaderCircle
                  v-if="store.scoring"
                  :size="17"
                  aria-hidden="true"
                />
                <RotateCcw
                  v-else-if="store.error === 'AI 服务暂时不可用'"
                  :size="17"
                  aria-hidden="true"
                />
                <Sparkles v-else :size="17" aria-hidden="true" />
                <span>{{ scoreActionLabel }}</span>
              </button>
            </div>

            <section
              v-if="store.current.scores && store.current.total_score !== null"
              data-test="simulation-score-result"
              class="score-result"
              aria-labelledby="score-result-title"
            >
              <h3 id="score-result-title">四维评分结果</h3>
              <div
                v-for="key in dimensions"
                :key="key"
                data-test="simulation-score-row"
                class="score-row"
              >
                <span data-test="simulation-score-label">
                  {{ dimensionLabels[key] }}
                </span>
                <strong data-test="simulation-score-value">
                  {{ store.current.scores[key] }}
                </strong>
                <p>{{ store.current.suggestions?.[key] }}</p>
              </div>
              <div class="total-score" data-test="simulation-total-score">
                <span>总分</span>
                <strong>{{ store.current.total_score }}</strong>
              </div>
            </section>
          </div>

          <p v-else class="empty-state">
            请从左侧选择一个场景开始独立训练。
          </p>
        </section>

        <aside class="panel history-panel" aria-labelledby="history-title">
          <div class="panel-heading">
            <History :size="18" aria-hidden="true" />
            <h2 id="history-title">训练历史</h2>
            <span>{{ store.history.length }} 条</span>
          </div>
          <ul v-if="store.history.length" data-test="simulation-history">
            <li v-for="item in store.history" :key="item.id">
              <button
                type="button"
                :data-test="`simulation-history-item-${item.id}`"
                :disabled="store.isBusy"
                @click="store.openTraining(item.id)"
              >
                <strong>{{ item.scene_label }}</strong>
                <span>{{ item.status === 'completed' ? '已评分' : '进行中' }}</span>
                <time :datetime="item.created_at">
                  {{ formatTime(item.created_at) }}
                </time>
                <em v-if="item.total_score !== null">
                  {{ item.total_score }} 分
                </em>
              </button>
            </li>
          </ul>
          <p v-else class="empty-state">暂无模拟训练记录。</p>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.simulation-page {
  min-width: 0;
  min-height: 100vh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.simulation-shell {
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.page-heading {
  max-width: 820px;
  margin-bottom: 28px;
}

.page-kicker {
  margin: 0 0 6px;
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 3.4rem);
  line-height: 1.05;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--ark-muted);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(210px, 0.62fr) minmax(360px, 1.65fr);
  gap: 16px;
  align-items: start;
}

.panel {
  min-width: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 50px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.panel-heading h2 {
  margin: 0;
  font-size: 0.96rem;
}

.panel-heading > span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.scene-panel,
.history-panel {
  position: sticky;
  top: 16px;
}

.scene-panel ul,
.history-panel ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 14px;
  list-style: none;
}

.scene-panel button,
.history-panel button {
  display: grid;
  width: 100%;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-align: left;
}

.scene-panel button {
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.scene-panel button:hover,
.scene-panel button:focus-visible,
.history-panel button:hover,
.history-panel button:focus-visible {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.scene-panel button.is-active {
  border-color: var(--ark-signal);
  background: var(--ark-surface-2);
}

.scene-panel button span,
.history-panel button strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-weight: 700;
}

.scene-panel button small,
.history-panel button span,
.history-panel button time {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.history-panel {
  position: static;
  grid-column: 1 / -1;
}

.history-panel button {
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 4px 14px;
  align-items: center;
}

.history-panel button em {
  color: var(--ark-state);
  font-size: 0.78rem;
  font-style: normal;
  font-weight: 700;
}

.history-panel button time {
  grid-column: 2 / -1;
}

.training-panel {
  min-height: 460px;
}

.active-scene {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.scene-heading {
  display: flex;
  gap: 16px;
  align-items: end;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ark-line);
}

.scene-heading p {
  margin: 0 0 2px;
  color: var(--ark-signal);
  font-size: 0.76rem;
  font-weight: 700;
}

.scene-heading h2 {
  margin: 0;
  font-size: 1.35rem;
}

.scene-heading time {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.segment-list {
  display: grid;
  gap: 12px;
}

.segment-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.segment-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.segment-heading h3 {
  margin: 0;
  font-size: 0.92rem;
}

.saved-mark {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  color: var(--ark-state);
  font-size: 0.76rem;
  font-weight: 700;
}

.segment-card textarea {
  width: 100%;
  min-height: 104px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  resize: vertical;
}

.segment-card textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.segment-card textarea:disabled {
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.segment-actions {
  display: flex;
  justify-content: flex-end;
}

.segment-actions button {
  min-height: 44px;
  padding: 8px 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-weight: 700;
}

.error-message {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.84rem;
}

.score-action {
  display: flex;
  gap: 18px;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.score-action strong {
  font-size: 0.92rem;
}

.score-action p {
  margin: 2px 0 0;
  color: var(--ark-muted);
  font-size: 0.8rem;
}

.score-action button {
  display: inline-flex;
  flex: 0 0 auto;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 16px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  font-weight: 700;
}

.score-result {
  display: grid;
  gap: 10px;
  padding-top: 4px;
}

.score-result h3 {
  margin: 0;
  font-size: 0.98rem;
}

.score-row {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) 56px minmax(0, 2fr);
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--ark-line);
}

.score-row > span {
  font-weight: 700;
}

.score-row > strong {
  color: var(--ark-signal);
  font-size: 1.1rem;
  text-align: right;
}

.score-row p {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.total-score {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 14px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-surface-2);
}

.total-score span {
  font-weight: 700;
}

.total-score strong {
  color: var(--ark-signal);
  font-size: 2rem;
  line-height: 1;
}

.empty-state {
  margin: 0;
  padding: 26px 18px;
  color: var(--ark-muted);
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .scene-panel {
    position: static;
  }

  .scene-panel ul {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .history-panel {
    grid-column: auto;
  }
}

@media (max-width: 560px) {
  .simulation-shell {
    padding: 28px 14px 56px;
  }

  .scene-panel ul {
    grid-template-columns: minmax(0, 1fr);
  }

  .scene-heading,
  .score-action {
    align-items: flex-start;
    flex-direction: column;
  }

  .score-action button {
    width: 100%;
  }

  .score-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .score-row p {
    grid-column: 1 / -1;
  }

  .history-panel button {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .history-panel button time {
    grid-column: 1 / -1;
  }
}
</style>
