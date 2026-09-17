<script setup lang="ts">
import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileDiff,
  History,
  Lightbulb,
  LoaderCircle,
  PenLine,
  Scale,
  Sparkles
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useEcommerceCopyTrainingStore } from '@/stores/ecommerceCopyTraining'

const store = useEcommerceCopyTrainingStore()
const auth = useAuthStore()
const router = useRouter()

const productTypeLabels: Record<string, string> = {
  food: '食品',
  craft: '手工艺品',
  agricultural_product: '农产品'
}

const sceneLabels: Record<string, string> = {
  social_commerce: '社交电商',
  product_page: '商品详情页',
  live_room: '直播间'
}

const optimizationSession = computed(() => {
  const current = store.current
  if (
    !current ||
    (
      current.status !== 'critique_ready' &&
      current.status !== 'copy_ready' &&
      current.status !== 'completed'
    )
  ) {
    return null
  }
  return current
})

const revisedCopyActionLabel = computed(() =>
  store.generatingCopy ? '生成中...' : '生成修订文案'
)

function productTypeLabel(value: string): string {
  return productTypeLabels[value] ?? value
}

function sceneLabel(value: string): string {
  return sceneLabels[value] ?? value
}

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

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void Promise.all([store.loadCatalog(), store.loadHistory()])
})
</script>

<template>
  <div class="copy-training-page">
    <AppHeader
      source="live"
      :loading="store.isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="copy-training-shell">
      <header class="page-heading">
        <p class="page-kicker">04 / 电商运营实训</p>
        <h1>文案提示词训练</h1>
        <p>
          从教学案例出发，先完成判断与参考对照，再<span
            class="page-heading__nowrap"
          >设计优化提示词</span>并检验新旧文案差异。
        </p>
      </header>

      <div class="workspace">
        <section
          data-test="copy-training-stage-selection"
          class="panel selection-panel"
          aria-labelledby="selection-title"
        >
          <div class="panel-heading">
            <Sparkles :size="18" aria-hidden="true" />
            <span class="stage-number">01</span>
            <h2 id="selection-title">选择商品与场景</h2>
            <span v-if="store.current" class="stage-state">已开始</span>
          </div>

          <form class="selection-form" @submit.prevent>
            <label>
              <span>商品类型</span>
              <select
                v-model="store.productType"
                data-test="copy-training-product-type"
              >
                <option
                  v-for="productType in store.catalog.product_types"
                  :key="productType"
                  :value="productType"
                >
                  {{ productTypeLabel(productType) }}
                </option>
              </select>
            </label>

            <label>
              <span>训练场景</span>
              <select
                v-model="store.scene"
                data-test="copy-training-scene"
              >
                <option
                  v-for="scene in store.catalog.scenes"
                  :key="scene"
                  :value="scene"
                >
                  {{ sceneLabel(scene) }}
                </option>
              </select>
            </label>

            <button
              type="button"
              data-test="copy-training-start"
              :disabled="!store.canStart"
              @click="store.create(store.productType, store.scene)"
            >
              <LoaderCircle
                v-if="store.creating"
                :size="17"
                aria-hidden="true"
              />
              <Sparkles v-else :size="17" aria-hidden="true" />
              <span>{{ store.creating ? '生成中...' : '生成教学案例' }}</span>
            </button>
          </form>
        </section>

        <section
          v-if="store.current"
          data-test="copy-training-stage-case"
          class="panel case-panel"
          aria-labelledby="case-title"
        >
          <div class="panel-heading">
            <PenLine :size="18" aria-hidden="true" />
            <span class="stage-number">02</span>
            <h2 id="case-title">教学案例</h2>
          </div>

          <article class="case-body">
            <p class="case-label">以下内容为明确标记的教学案例</p>
            <p data-test="copy-training-case-copy" class="case-copy">
              {{ store.current.case.copy_text }}
            </p>
            <div
              v-if="store.current.case.defect_categories?.length"
              class="defect-list"
            >
              <span
                v-for="category in store.current.case.defect_categories"
                :key="category"
              >
                {{ category }}
              </span>
            </div>
          </article>
        </section>

        <section
          v-if="store.current?.status === 'case_ready'"
          data-test="copy-training-stage-critique"
          class="panel critique-panel"
          aria-labelledby="critique-title"
        >
          <div class="panel-heading">
            <ClipboardCheck :size="18" aria-hidden="true" />
            <span class="stage-number">03</span>
            <h2 id="critique-title">学员评判</h2>
          </div>

          <div class="step-body">
            <label class="field-label" for="copy-training-critique">
              指出案例中的问题并说明理由
            </label>
            <textarea
              id="copy-training-critique"
              v-model="store.critiqueDraft"
              data-test="copy-training-critique"
              rows="5"
              placeholder="例如：缺少规格与行动指令，购买理由不够明确"
            />
            <div class="step-actions">
              <button
                type="button"
                data-test="copy-training-submit-critique"
                :disabled="!store.canSubmitCritique"
                @click="store.submitCritique(store.critiqueDraft)"
              >
                <LoaderCircle
                  v-if="store.submittingCritique"
                  :size="17"
                  aria-hidden="true"
                />
                <ArrowRight v-else :size="17" aria-hidden="true" />
                <span>
                  {{
                    store.submittingCritique
                      ? '对照中...'
                      : store.error === 'AI 服务暂时不可用'
                        ? '重试提交评判'
                        : '提交评判'
                  }}
                </span>
              </button>
            </div>
          </div>
        </section>

        <section
          v-if="store.current?.reference"
          data-test="copy-training-stage-comparison"
          class="panel comparison-panel"
          aria-labelledby="comparison-title"
        >
          <div class="panel-heading">
            <Scale :size="18" aria-hidden="true" />
            <span class="stage-number">04</span>
            <h2 id="comparison-title">评判对照与一致性</h2>
          </div>

          <div
            data-test="copy-training-comparison"
            class="comparison-grid"
          >
            <article>
              <h3>学员评判</h3>
              <p>{{ store.current.learner_critique }}</p>
            </article>
            <article>
              <h3>参考评判</h3>
              <p>{{ store.current.reference.reference_critique }}</p>
            </article>
          </div>

          <div class="score-strip">
            <div>
              <span>一致性分</span>
              <strong data-test="copy-training-consistency-score">
                {{ store.current.reference.consistency_score }}
              </strong>
            </div>
            <p data-test="copy-training-consistency-reason">
              {{ store.current.reference.reason }}
            </p>
          </div>
        </section>

        <section
          v-if="optimizationSession"
          data-test="copy-training-stage-optimization"
          class="panel optimization-panel"
          aria-labelledby="optimization-title"
        >
          <div class="panel-heading">
            <Lightbulb :size="18" aria-hidden="true" />
            <span class="stage-number">05</span>
            <h2 id="optimization-title">优化提示词与文案对比</h2>
          </div>

          <div class="optimization-body">
            <label class="field-label" for="copy-training-optimized-prompt">
              优化提示词
            </label>
            <textarea
              id="copy-training-optimized-prompt"
              v-model="store.optimizedPrompt"
              data-test="copy-training-optimized-prompt"
              rows="4"
              :readonly="optimizationSession.status !== 'critique_ready'"
              placeholder="说明希望补充的信息、表达方式和行动指令"
            />

            <div
              v-if="optimizationSession.status === 'critique_ready'"
              class="step-actions"
            >
              <button
                type="button"
                data-test="copy-training-generate-revised"
                :disabled="!store.canGenerateCopy"
                @click="store.generateCopy(store.optimizedPrompt)"
              >
                <LoaderCircle
                  v-if="store.generatingCopy"
                  :size="17"
                  aria-hidden="true"
                />
                <FileDiff v-else :size="17" aria-hidden="true" />
                <span>{{ revisedCopyActionLabel }}</span>
              </button>
            </div>

            <div
              v-if="
                optimizationSession.status === 'copy_ready' ||
                optimizationSession.status === 'completed'
              "
              class="copy-comparison"
            >
              <article data-test="copy-training-old-copy">
                <h3>原教学案例</h3>
                <p>{{ optimizationSession.case.copy_text }}</p>
              </article>
              <article data-test="copy-training-new-copy">
                <h3>修订文案</h3>
                <p>{{ optimizationSession.revised_copy }}</p>
              </article>
            </div>

            <div
              v-if="
                optimizationSession.status === 'copy_ready' ||
                optimizationSession.status === 'completed'
              "
              data-test="copy-training-differences"
              class="differences"
            >
              <h3>可见差异</h3>
              <ul v-if="optimizationSession.optimization">
                <li
                  v-for="difference in optimizationSession.optimization.differences"
                  :key="difference"
                >
                  {{ difference }}
                </li>
              </ul>
              <p v-else>
                修订文案已生成，等待 AI 对照新旧版本并给出优化效果证据。
              </p>
            </div>

            <div
              v-if="optimizationSession.status === 'copy_ready'"
              class="step-actions"
            >
              <button
                type="button"
                data-test="copy-training-generate-optimization"
                :disabled="!store.canGenerateOptimization"
                @click="store.generateOptimization()"
              >
                <LoaderCircle
                  v-if="store.generatingOptimization"
                  :size="17"
                  aria-hidden="true"
                />
                <Scale v-else :size="17" aria-hidden="true" />
                <span>
                  {{
                    store.generatingOptimization
                      ? '分析中...'
                      : store.error === 'AI 服务暂时不可用'
                        ? '重试优化点评'
                        : '生成优化点评'
                  }}
                </span>
              </button>
            </div>

            <div
              v-if="
                optimizationSession.status === 'completed' &&
                optimizationSession.optimization
              "
              data-test="copy-training-optimization-result"
              class="optimization-result"
            >
              <div>
                <span>优化效果</span>
                <strong data-test="copy-training-optimization-score">
                  {{ optimizationSession.optimization.optimization_score }}
                </strong>
              </div>
              <p data-test="copy-training-optimization-evidence">
                {{ optimizationSession.optimization.evidence }}
              </p>
              <span class="completed-mark">
                <CheckCircle2 :size="16" aria-hidden="true" />
                训练已完成
              </span>
            </div>
          </div>
        </section>

        <aside class="panel history-panel" aria-labelledby="history-title">
          <div class="panel-heading">
            <History :size="18" aria-hidden="true" />
            <h2 id="history-title">训练历史</h2>
            <span>{{ store.history.length }} 条</span>
          </div>

          <ul v-if="store.history.length" data-test="copy-training-history">
            <li
              v-for="item in store.history"
              :key="item.id"
            >
              <button
                type="button"
                :data-test="`copy-training-history-item-${item.id}`"
                :disabled="store.isBusy"
                @click="store.openSession(item.id)"
              >
                <span>
                  {{ productTypeLabel(item.product_type) }}
                  ·
                  {{ sceneLabel(item.scene) }}
                </span>
                <time :datetime="item.created_at">
                  {{ formatTime(item.created_at) }}
                </time>
                <span class="history-status">
                  {{ item.status === 'completed' ? '已完成' : '进行中' }}
                </span>
              </button>
            </li>
          </ul>
          <p v-else class="empty-state">暂无文案训练记录。</p>
        </aside>
      </div>

      <p
        v-if="store.error"
        class="error-message"
        role="alert"
        aria-live="assertive"
      >
        {{ store.error }}
      </p>
    </main>
  </div>
</template>

<style scoped>
.copy-training-page {
  min-width: 0;
  min-height: 100vh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.copy-training-shell {
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

.page-heading__nowrap {
  white-space: nowrap;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--ark-muted);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
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

.panel-heading > span:last-child {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.stage-number {
  color: var(--ark-signal);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0;
}

.stage-state {
  color: var(--ark-state) !important;
  font-weight: 700;
}

.selection-form {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 18px;
}

.selection-form label {
  display: grid;
  gap: 7px;
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.selection-form select,
.field-label + textarea {
  width: 100%;
  min-height: 42px;
  padding: 10px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.selection-form select:focus,
.field-label + textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.selection-form button,
.step-actions button {
  display: inline-flex;
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

.selection-form button:disabled,
.step-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.case-body,
.step-body,
.optimization-body {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.case-label {
  width: fit-content;
  margin: 0;
  padding: 5px 8px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.76rem;
  font-weight: 700;
}

.case-copy,
.comparison-grid p,
.copy-comparison p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.case-copy {
  padding: 18px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
  font-size: 1.08rem;
}

.defect-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.defect-list span {
  padding: 4px 8px;
  border: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.field-label {
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.field-label + textarea {
  min-height: 112px;
  resize: vertical;
}

.field-label + textarea[readonly] {
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.step-actions {
  display: flex;
  justify-content: flex-end;
}

.comparison-grid,
.copy-comparison {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 18px;
}

.comparison-grid article,
.copy-comparison article {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.comparison-grid h3,
.copy-comparison h3,
.differences h3 {
  margin: 0 0 8px;
  font-size: 0.86rem;
}

.score-strip,
.optimization-result {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 18px;
  align-items: center;
  margin: 0 18px 18px;
  padding: 14px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-surface-2);
}

.score-strip > div,
.optimization-result > div {
  display: grid;
  gap: 2px;
}

.score-strip span,
.optimization-result > div span {
  color: var(--ark-muted);
  font-size: 0.76rem;
  font-weight: 700;
}

.score-strip strong,
.optimization-result strong {
  color: var(--ark-signal);
  font-size: 2rem;
  line-height: 1;
}

.score-strip p,
.optimization-result p {
  margin: 0;
  color: var(--ark-paper);
}

.copy-comparison {
  padding: 0;
}

.differences {
  padding: 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.differences ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 20px;
  color: var(--ark-muted);
}

.differences p {
  margin: 0;
  color: var(--ark-muted);
}

.optimization-result {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.completed-mark {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ark-state);
  font-size: 0.8rem;
  font-weight: 700;
}

.history-panel ul {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 14px;
  list-style: none;
}

.history-panel button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 5px 12px;
  width: 100%;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-align: left;
}

.history-panel button:hover,
.history-panel button:focus-visible {
  border-color: var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.history-panel button > span:first-child {
  min-width: 0;
  overflow-wrap: anywhere;
  font-weight: 700;
}

.history-panel time,
.history-status {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.history-status {
  color: var(--ark-state);
  font-weight: 700;
}

.empty-state {
  margin: 0;
  padding: 26px 18px;
  color: var(--ark-muted);
}

.error-message {
  margin: 16px 0 0;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.84rem;
}

@media (max-width: 760px) {
  .selection-form {
    grid-template-columns: minmax(0, 1fr);
  }

  .selection-form button,
  .step-actions button {
    width: 100%;
  }

  .comparison-grid,
  .copy-comparison {
    grid-template-columns: minmax(0, 1fr);
  }

  .score-strip,
  .optimization-result {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 540px) {
  .copy-training-shell {
    padding: 28px 14px 56px;
  }

  .panel-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .panel-heading > span:last-child {
    width: 100%;
    margin-left: 0;
  }

  .history-panel button {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
