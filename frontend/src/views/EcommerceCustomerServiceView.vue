<script setup lang="ts">
import {
  CheckCircle2,
  MessagesSquare,
  Send,
  Target
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import type { CustomerSession } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useEcommerceCustomerServiceStore } from '@/stores/ecommerceCustomerService'

const store = useEcommerceCustomerServiceStore()
const auth = useAuthStore()
const router = useRouter()

const criterionLabels: Record<string, string> = {
  product_need_identified: '识别商品需求',
  accurate_info_and_next_step: '提供准确信息与下一步',
  promotion_rule_explained: '说明优惠规则',
  eligibility_verified: '确认参与资格',
  order_context_identified: '确认订单与物流背景',
  delivery_and_next_step: '说明时效与下一步',
  issue_identified: '明确售后问题',
  policy_and_process_explained: '说明政策与处理流程',
  emotion_acknowledged: '回应顾客情绪',
  resolution_or_escalation: '给出解决或升级路径'
}

function criterionLabel(value: string): string {
  const normalized = value.trim()
  if (!normalized) {
    return '训练目标'
  }
  return (
    criterionLabels[normalized] ??
    (/^[a-z][a-z0-9_]*$/.test(normalized) ? '训练目标' : normalized)
  )
}

const lastTurn = computed(() => {
  const turns = store.currentSession?.turns
  return turns?.length ? turns[turns.length - 1] : null
})
const canCompose = computed(
  () =>
    Boolean(
      store.currentSession &&
        store.currentSession.status !== 'completed' &&
        !store.currentSession.end_suggested &&
        lastTurn.value &&
        !lastTurn.value.student_reply
  )
)
const operationStatus = computed(() => {
  if (store.loadingScenarios && !store.scenarios.length) {
    return '正在加载客服训练场景'
  }
  if (store.loadingHistory && !store.history.length) {
    return '正在加载客服训练历史'
  }
  if (store.starting) {
    return '正在生成客户消息'
  }
  if (store.submitting) {
    return '正在分析学员回复'
  }
  if (store.advancing) {
    return '正在生成下一条客户消息'
  }
  if (store.ending) {
    return '正在生成训练总结'
  }
  return store.currentSession?.status === 'completed' ? '客服训练已完成' : ''
})

function formatValue(value: unknown, depth = 0): string {
  if (value === null || value === undefined) {
    return '未提供'
  }
  if (typeof value === 'string') {
    return value.trim() || '未提供'
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    const parts = value
      .map(item => formatValue(item, depth + 1))
      .filter(item => item !== '未提供')
    return parts.length ? parts.join('、') : '未提供'
  }
  if (typeof value === 'object') {
    if (depth >= 3) {
      return '复杂内容'
    }

    const parts = Object.entries(value as Record<string, unknown>).map(
      ([key, item]) => `${key}：${formatValue(item, depth + 1)}`
    )
    return parts.length ? parts.join('；') : '未提供'
  }
  return String(value)
}

function criterionStatus(value: unknown): string {
  if (value === true) {
    return '已达成'
  }
  if (value === false) {
    return '未达成'
  }
  return formatValue(value)
}

function goalStatusLabel(value: 'reached' | 'not_reached'): string {
  return value === 'reached' ? '目标已达成' : '目标未达成'
}

function historyStatusLabel(status: CustomerSession['status']): string {
  if (status === 'completed') {
    return '已完成'
  }
  if (status === 'goal_reached') {
    return '待确认结束'
  }
  return '进行中'
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
}

function historySummary(session: {
  status: CustomerSession['status']
  summary: { goal_completion: unknown } | null
}): string {
  if (session.summary) {
    return formatValue(session.summary.goal_completion)
  }
  return session.status === 'completed'
    ? '训练已完成'
    : '尚未生成训练总结'
}

function scenarioIsActive(key: string): boolean {
  return store.currentSession?.scenario_key === key
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void Promise.all([store.loadScenarios(), store.loadHistory()])
})
</script>

<template>
  <div class="customer-service-page">
    <AppHeader
      source="live"
      :loading="store.isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="customer-service-shell" :aria-busy="store.isBusy">
      <p
        data-test="customer-service-operation-status"
        class="ark-sr-only"
        role="status"
        aria-live="polite"
      >
        {{ operationStatus }}
      </p>

      <header class="page-heading">
        <p class="page-kicker">04 / 电商运营实训</p>
        <h1>客服模拟训练</h1>
        <p>
          AI 扮演客户发起咨询，每轮回复后给出证据、建议与目标状态；只有由你确认后才会结束。
        </p>
      </header>

      <section
        data-test="customer-service-scenario-region"
        :aria-busy="store.loadingScenarios"
        aria-labelledby="scenario-title"
      >
        <div class="section-heading">
          <div>
            <span>训练场景</span>
            <h2 id="scenario-title">选择一种咨询目标</h2>
          </div>
          <small>每个场景至少包含两项达成标准</small>
        </div>

        <div v-if="store.scenarios.length" class="scenario-grid">
          <article
            v-for="scenario in store.scenarios"
            :key="scenario.key"
            data-test="customer-service-scenario"
            class="scenario-card"
            :class="{ active: scenarioIsActive(scenario.key) }"
          >
            <button
              type="button"
              :data-test="`customer-service-scenario-${scenario.key}`"
              :disabled="store.isBusy"
              @click="store.start(scenario.key)"
            >
              <MessagesSquare :size="20" aria-hidden="true" />
              <h2>{{ scenario.label }}</h2>
              <ul>
                <li v-for="criterion in scenario.criteria" :key="criterion">
                  {{ criterionLabel(criterion) }}
                </li>
              </ul>
              <span class="scenario-action">
                {{ scenarioIsActive(scenario.key) ? '重新开始' : '开始训练' }}
              </span>
            </button>
          </article>
        </div>
        <p v-else-if="!store.loadingScenarios" class="empty-state">
          暂无客服训练场景。
        </p>
      </section>

      <section
        class="history-panel"
        data-test="customer-service-history-region"
        :aria-busy="store.loadingHistory"
        aria-labelledby="history-title"
      >
        <div class="section-heading">
          <div>
            <span>训练记录</span>
            <h2 id="history-title">客服历史</h2>
          </div>
          <small>{{ store.historyItems.length }} 条记录</small>
        </div>

        <div
          v-if="store.historyItems.length"
          class="history-list"
          data-test="customer-service-history"
        >
          <button
            v-for="session in store.historyItems"
            :key="session.id"
            type="button"
            :data-test="`customer-service-history-item-${session.id}`"
            :disabled="store.isBusy"
            @click="store.openSession(session.id)"
          >
            <span class="history-main">
              <strong>{{ session.scenario_label }}</strong>
              <small>{{ historyStatusLabel(session.status) }}</small>
            </span>
            <time :datetime="session.updated_at">
              {{ formatTime(session.updated_at) }}
            </time>
            <span class="history-result">{{ historySummary(session) }}</span>
          </button>
        </div>
        <p v-else-if="!store.loadingHistory" class="empty-state">
          暂无客服训练记录。
        </p>
      </section>

      <p
        v-if="store.error"
        class="error-message"
        role="alert"
        aria-live="assertive"
      >
        {{ store.error }}
      </p>

      <section
        v-if="store.currentSession"
        data-test="customer-service-conversation"
        class="conversation panel"
        :aria-busy="store.submitting || store.advancing || store.ending"
        aria-labelledby="conversation-title"
      >
        <div class="panel-heading">
          <MessagesSquare :size="19" aria-hidden="true" />
          <div>
            <h2 id="conversation-title">
              {{ store.currentSession.scenario_label }}
            </h2>
            <span>
              {{
                store.currentSession.status === 'completed'
                  ? '训练已完成'
                  : store.currentSession.end_suggested
                    ? 'AI 建议结束，等待你确认'
                    : '训练进行中'
              }}
            </span>
          </div>
          <div class="goal-summary">
            <Target :size="17" aria-hidden="true" />
            <span>目标标准</span>
          </div>
        </div>

        <div class="goal-criteria">
          <span
            v-for="criterion in store.currentSession.goal_criteria"
            :key="criterion"
          >
            {{ criterionLabel(criterion) }}
          </span>
        </div>

        <ol
          data-test="customer-service-transcript"
          class="transcript"
        >
          <li
            v-for="turn in store.currentSession.turns"
            :key="turn.id"
            data-test="customer-service-turn"
            class="turn"
          >
            <article class="message customer-message">
              <span class="message-label">客户</span>
              <p>{{ formatValue(turn.customer_message) }}</p>
            </article>

            <article
              v-if="turn.student_reply"
              class="message student-message"
            >
              <span class="message-label">学员</span>
              <p>{{ formatValue(turn.student_reply) }}</p>
            </article>

            <section v-if="turn.analysis" class="turn-analysis">
              <div class="analysis-heading">
                <h3>本轮分析</h3>
                <span
                  class="goal-status"
                  :class="turn.analysis.goal_status"
                >
                  {{ goalStatusLabel(turn.analysis.goal_status) }}
                </span>
              </div>

              <dl>
                <div>
                  <dt>问题</dt>
                  <dd>{{ formatValue(turn.analysis.problem) }}</dd>
                </div>
                <div>
                  <dt>证据</dt>
                  <dd>{{ formatValue(turn.analysis.evidence) }}</dd>
                </div>
                <div>
                  <dt>建议</dt>
                  <dd>{{ formatValue(turn.analysis.suggestion) }}</dd>
                </div>
              </dl>

              <div class="criterion-results">
                <span
                  v-for="(value, criterion) in turn.analysis.criteria"
                  :key="criterion"
                >
                  <strong>{{ criterionLabel(criterion) }}</strong>
                  <small>{{ criterionStatus(value) }}</small>
                </span>
              </div>
            </section>
          </li>
        </ol>

        <form
          v-if="canCompose"
          class="reply-form"
          @submit.prevent="store.submitReply(store.pendingReply)"
        >
          <label for="customer-service-reply">你的回复</label>
          <textarea
            id="customer-service-reply"
            v-model="store.pendingReply"
            data-test="customer-service-reply"
            rows="4"
            placeholder="结合客户当前问题，写出你的客服回复。"
          />
          <button
            type="submit"
            data-test="customer-service-submit"
            :disabled="store.submitting || !store.pendingReply.trim()"
          >
            <Send :size="17" aria-hidden="true" />
            <span>{{ store.submitting ? '分析中...' : '提交回复' }}</span>
          </button>
        </form>

        <div class="conversation-actions">
          <button
            v-if="store.canContinue"
            type="button"
            data-test="customer-service-continue"
            class="continue-action"
            :disabled="store.advancing"
            @click="store.nextMessage()"
          >
            <MessagesSquare :size="17" aria-hidden="true" />
            <span>{{ store.advancing ? '客户输入中...' : '继续客户消息' }}</span>
          </button>

          <button
            v-if="store.canEnd"
            type="button"
            data-test="customer-service-end"
            class="end-action"
            :disabled="store.ending"
            @click="store.confirmEnd()"
          >
            <CheckCircle2 :size="17" aria-hidden="true" />
            <span>{{ store.ending ? '生成总结中...' : '结束训练' }}</span>
          </button>
        </div>
      </section>

      <section
        v-if="store.currentSession?.summary"
        class="summary panel"
        :aria-busy="store.ending"
        aria-labelledby="summary-title"
      >
        <div class="panel-heading">
          <CheckCircle2 :size="19" aria-hidden="true" />
          <h2 id="summary-title">训练总结</h2>
        </div>

        <div class="summary-grid">
          <article>
            <h3>整场表现</h3>
            <p>
              {{ formatValue(store.currentSession.summary.overall_performance) }}
            </p>
          </article>
          <article>
            <h3>主要问题</h3>
            <p>
              {{ formatValue(store.currentSession.summary.main_problems) }}
            </p>
          </article>
          <article>
            <h3>优先改进项</h3>
            <p>
              {{
                formatValue(
                  store.currentSession.summary.prioritized_improvements
                )
              }}
            </p>
          </article>
          <article>
            <h3>目标完成情况</h3>
            <p>
              {{ formatValue(store.currentSession.summary.goal_completion) }}
            </p>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.customer-service-page {
  min-width: 0;
  min-height: 100vh;
  overflow-x: clip;
  color-scheme: light;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.customer-service-shell {
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.page-heading {
  max-width: 820px;
  margin-bottom: 30px;
}

.page-heading h1 {
  margin: 0;
  font-size: 3.2rem;
  line-height: 1.08;
  text-wrap: balance;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.page-kicker,
.section-heading > div > span {
  color: var(--ark-signal);
  font-size: 0.78rem;
  font-weight: 800;
}

.page-kicker {
  margin: 0 0 6px;
}

.section-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  align-items: end;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin: 4px 0 0;
  font-size: 1.55rem;
}

.section-heading small {
  color: var(--ark-muted);
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.scenario-card {
  min-width: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.scenario-card.active {
  border-color: var(--ark-signal);
}

.scenario-card button {
  display: grid;
  gap: 10px;
  width: 100%;
  min-height: 190px;
  padding: 16px;
  border: 0;
  background: transparent;
  color: var(--ark-paper);
  text-align: left;
}

.scenario-card button:hover,
.scenario-card button:focus-visible {
  background: var(--ark-surface-1);
}

.scenario-card h2 {
  margin: 0;
  font-size: 1rem;
}

.scenario-card ul {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  list-style: none;
}

.scenario-card li::before {
  content: "·";
  margin-right: 5px;
  color: var(--ark-signal);
}

.scenario-action {
  align-self: end;
  color: var(--ark-signal);
  font-size: 0.8rem;
  font-weight: 800;
}

.history-panel {
  margin-top: 28px;
}

.history-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 9px;
}

.history-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 5px 12px;
  min-width: 0;
  padding: 13px 14px;
  border: 1px solid var(--ark-line);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-align: left;
}

.history-list button:hover,
.history-list button:focus-visible {
  border-color: var(--ark-signal);
  background: var(--ark-surface-1);
}

.history-main {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.history-main strong {
  overflow-wrap: anywhere;
}

.history-main small,
.history-result {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.history-list time {
  color: var(--ark-muted);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.history-result {
  grid-column: 1 / -1;
  overflow-wrap: anywhere;
}

.error-message {
  margin: 16px 0 0;
  padding: 11px 13px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.panel {
  min-width: 0;
  margin-top: 16px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.panel-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 58px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.panel-heading h2 {
  margin: 0;
  font-size: 1rem;
}

.panel-heading span {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.goal-summary {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  margin-left: auto;
  color: var(--ark-signal);
}

.goal-criteria {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.goal-criteria span {
  padding: 5px 8px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.transcript {
  display: grid;
  gap: 22px;
  margin: 0;
  padding: 20px 16px;
  list-style: none;
}

.turn {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.message {
  width: min(100%, 760px);
  padding: 12px 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.message p {
  margin: 5px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.message-label {
  color: var(--ark-signal);
  font-size: 0.75rem;
  font-weight: 800;
}

.customer-message {
  justify-self: start;
  background: var(--ark-surface-1);
}

.student-message {
  justify-self: end;
  border-color: var(--ark-line-strong);
}

.turn-analysis {
  padding: 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.analysis-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.analysis-heading h3 {
  margin: 0;
  font-size: 0.92rem;
}

.goal-status {
  padding: 3px 7px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  font-size: 0.74rem;
  font-weight: 800;
}

.goal-status.reached {
  border-color: var(--ark-state);
  color: var(--ark-state);
}

.turn-analysis dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0 0;
}

.turn-analysis dl > div {
  min-width: 0;
}

.turn-analysis dt {
  color: var(--ark-signal);
  font-size: 0.76rem;
  font-weight: 800;
}

.turn-analysis dd {
  margin: 4px 0 0;
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.criterion-results {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 7px;
  margin-top: 12px;
}

.criterion-results > span {
  display: grid;
  gap: 1px;
  padding: 8px 9px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.criterion-results strong {
  font-size: 0.78rem;
}

.criterion-results small {
  color: var(--ark-muted);
  overflow-wrap: anywhere;
}

.reply-form {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid var(--ark-line);
}

.reply-form label {
  color: var(--ark-muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.reply-form textarea {
  width: 100%;
  min-height: 112px;
  padding: 11px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  outline: none;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  resize: vertical;
}

.reply-form textarea:focus {
  border-color: var(--ark-focus);
  box-shadow: 0 0 0 2px var(--ark-surface-2);
}

.reply-form button,
.conversation-actions button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--ark-radius);
  font-weight: 800;
}

.reply-form button {
  justify-self: end;
  padding-inline: 18px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.conversation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  padding: 0 16px 16px;
}

.continue-action {
  padding-inline: 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.end-action {
  padding-inline: 16px;
  border: 1px solid var(--ark-state);
  background: var(--ark-state);
  color: var(--ark-surface-0);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-grid article {
  min-width: 0;
  padding: 18px;
  border-right: 1px solid var(--ark-line);
  border-bottom: 1px solid var(--ark-line);
}

.summary-grid article:nth-child(2n) {
  border-right: 0;
}

.summary-grid article:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.summary-grid h3 {
  margin: 0;
  color: var(--ark-signal);
  font-size: 0.95rem;
}

.summary-grid p {
  margin: 8px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.empty-state {
  margin: 0;
  padding: 24px 16px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

@media (max-width: 1120px) {
  .scenario-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .customer-service-shell {
    padding: 28px 14px 56px;
  }

  .page-heading h1 {
    font-size: 2.35rem;
  }

  .scenario-grid,
  .turn-analysis dl,
  .summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .scenario-card button {
    min-height: 0;
  }

  .goal-summary {
    display: none;
  }

  .summary-grid article,
  .summary-grid article:nth-child(2n),
  .summary-grid article:nth-last-child(-n + 2) {
    border-right: 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .summary-grid article:last-child {
    border-bottom: 0;
  }
}
</style>
