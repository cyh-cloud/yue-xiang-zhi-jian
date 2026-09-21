<script setup lang="ts">
import {
  Check,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import type {
  AdminPointsExpiryMode,
  AdminPointsPolicy,
  AdminPointsPolicyPayload,
  AdminTrainingWeightKey,
  AdminTrainingWeights
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

interface WeightField {
  key: AdminTrainingWeightKey
  slug: string
  label: string
}

const weightFields: ReadonlyArray<WeightField> = [
  { key: 'default', slug: 'default', label: '通用训练' },
  { key: 'live_script', slug: 'live-script', label: '直播话术' },
  { key: 'simulation', slug: 'simulation', label: '模拟训练' },
  { key: 'copy_training', slug: 'copy-training', label: '文案训练' },
  { key: 'customer_service', slug: 'customer-service', label: '客服训练' }
]

const expiryOptions: ReadonlyArray<{
  value: AdminPointsExpiryMode
  slug: string
  label: string
}> = [
  { value: 'permanent', slug: 'permanent', label: '永久有效' },
  { value: 'natural_year', slug: 'natural-year', label: '自然年清零' }
]

const store = useAdminConsoleStore()
const secondsPerPoint = ref('')
const dailyLimit = ref('')
const trainingWeights = reactive<Record<AdminTrainingWeightKey, string>>({
  default: '',
  live_script: '',
  simulation: '',
  copy_training: '',
  customer_service: ''
})
const expiryMode = ref<AdminPointsExpiryMode>('permanent')
const policyVersion = ref<number | null>(null)
const fieldErrors = ref<Record<string, string>>({})
const successMessage = ref('')

const updatedByLabel = computed(() => {
  const policy = store.pointsPolicy
  if (!policy) return ''
  return policy.updated_by === 0 ? '系统初始化' : `#${policy.updated_by}`
})

function formatTime(value: string | null): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

function parsePositiveInt(raw: string | number): number | null {
  // A `type="number"` input binds a number once it holds a valid value and a
  // string while it is empty, so both shapes reach the validator.
  if (typeof raw === 'number') {
    return Number.isInteger(raw) && raw >= 1 ? raw : null
  }
  const trimmed = raw.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const value = Number(trimmed)
  if (!Number.isInteger(value) || value < 1) return null
  return value
}

function seedForm(policy: AdminPointsPolicy): void {
  secondsPerPoint.value = String(policy.seconds_per_point)
  trainingWeights.default = String(policy.training_weights.default)
  trainingWeights.live_script = String(policy.training_weights.live_script)
  trainingWeights.simulation = String(policy.training_weights.simulation)
  trainingWeights.copy_training = String(policy.training_weights.copy_training)
  trainingWeights.customer_service = String(
    policy.training_weights.customer_service
  )
  dailyLimit.value = String(policy.daily_limit)
  expiryMode.value = policy.expiry_mode
  policyVersion.value = policy.version
}

function clearFormError(): void {
  // A failed save leaves its banner up, but the next keystroke starts a new
  // attempt: retire the stale conflict or validation message so it never
  // outlives the edit it described. Re-seeding from the server assigns the
  // refs directly and raises no input event, so the 409 reload keeps its
  // banner.
  store.clearPointsPolicyFormError()
}

async function submitPolicy(): Promise<void> {
  if (policyVersion.value === null) return
  successMessage.value = ''
  const nextErrors: Record<string, string> = {}
  const seconds = parsePositiveInt(secondsPerPoint.value)
  if (seconds === null) {
    nextErrors.seconds_per_point = '需为不小于 1 的整数'
  }
  const weights: AdminTrainingWeights = {
    default: 0,
    live_script: 0,
    simulation: 0,
    copy_training: 0,
    customer_service: 0
  }
  for (const field of weightFields) {
    const parsed = parsePositiveInt(trainingWeights[field.key])
    if (parsed === null) {
      nextErrors[`training_weights.${field.key}`] = '需为不小于 1 的整数'
    } else {
      weights[field.key] = parsed
    }
  }
  const limit = parsePositiveInt(dailyLimit.value)
  if (limit === null) {
    nextErrors.daily_limit = '需为不小于 1 的整数'
  }
  if (seconds === null || limit === null || Object.keys(nextErrors).length > 0) {
    fieldErrors.value = nextErrors
    return
  }
  fieldErrors.value = {}
  const payload: AdminPointsPolicyPayload = {
    expected_version: policyVersion.value,
    seconds_per_point: seconds,
    training_weights: weights,
    daily_limit: limit,
    expiry_mode: expiryMode.value
  }
  const done = await store.savePointsPolicy(payload)
  if (done) {
    successMessage.value = '已保存积分规则'
  }
}

watch(
  () => store.pointsPolicy,
  policy => {
    // Seeding on every server policy keeps the form aligned with the row: the
    // first read fills the controls, and a 409 reload re-seeds them from the
    // authoritative values together with the bumped optimistic-lock version.
    if (policy) seedForm(policy)
  }
)

onMounted(() => {
  void store.loadPointsPolicy()
})
</script>

<template>
  <section class="admin-points-policy" data-test="admin-points-policy">
    <header class="pp-header">
      <div class="pp-header__identity">
        <SlidersHorizontal :size="26" aria-hidden="true" />
        <div>
          <h1>积分规则</h1>
          <p>配置平台积分发放速率、训练权重、每日上限与有效期，仅超级管理员可修改。</p>
        </div>
      </div>
      <dl v-if="store.pointsPolicy" class="pp-header__summary">
        <div>
          <dt>规则版本</dt>
          <dd class="ark-data" data-test="policy-rule-version">
            {{ store.pointsPolicy.rule_version }}
          </dd>
        </div>
        <div>
          <dt>最近更新</dt>
          <dd class="ark-data" data-test="policy-updated-at">
            {{ formatTime(store.pointsPolicy.updated_at) }}
          </dd>
        </div>
        <div>
          <dt>更新人</dt>
          <dd class="ark-data" data-test="policy-updated-by">
            {{ updatedByLabel }}
          </dd>
        </div>
      </dl>
    </header>

    <div
      v-if="store.pointsPolicyLoading && !store.pointsPolicy"
      class="pp-state"
      data-test="points-policy-loading"
      role="status"
    >
      <RefreshCw class="spinning" :size="20" aria-hidden="true" />
      正在加载积分规则
    </div>

    <div
      v-if="store.pointsPolicyError"
      class="pp-error"
      data-test="points-policy-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.pointsPolicyError }}</span>
      <button
        type="button"
        data-test="points-policy-retry"
        :disabled="store.pointsPolicyLoading"
        @click="store.loadPointsPolicy()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <form
      class="pp-form"
      data-test="points-policy-form"
      novalidate
      v-if="store.pointsPolicy"
      @submit.prevent="submitPolicy"
    >
      <header class="pp-form__heading">
        <SlidersHorizontal :size="20" aria-hidden="true" />
        <h2>规则配置</h2>
        <span>所有权重与上限均为不小于 1 的整数。</span>
      </header>

      <div class="pp-scalars">
        <label class="pp-field">
          <span>每积分所需秒数</span>
          <input
            v-model="secondsPerPoint"
            type="number"
            min="1"
            step="1"
            data-test="seconds-per-point"
            inputmode="numeric"
            @input="clearFormError"
          />
          <span
            v-if="fieldErrors.seconds_per_point"
            class="pp-field__error"
            data-test="seconds-per-point-error"
          >
            {{ fieldErrors.seconds_per_point }}
          </span>
        </label>
        <label class="pp-field">
          <span>每日积分上限</span>
          <input
            v-model="dailyLimit"
            type="number"
            min="1"
            step="1"
            data-test="daily-limit"
            inputmode="numeric"
            @input="clearFormError"
          />
          <span
            v-if="fieldErrors.daily_limit"
            class="pp-field__error"
            data-test="daily-limit-error"
          >
            {{ fieldErrors.daily_limit }}
          </span>
        </label>
      </div>

      <div class="pp-weights">
        <p class="pp-weights__legend">训练积分权重</p>
        <div class="pp-form__grid">
          <label v-for="field in weightFields" :key="field.key" class="pp-field">
            <span>{{ field.label }}</span>
            <input
              v-model="trainingWeights[field.key]"
              type="number"
              min="1"
              step="1"
              :data-test="`weight-${field.slug}`"
              inputmode="numeric"
              @input="clearFormError"
            />
            <span
              v-if="fieldErrors[`training_weights.${field.key}`]"
              class="pp-field__error"
              :data-test="`weight-${field.slug}-error`"
            >
              {{ fieldErrors[`training_weights.${field.key}`] }}
            </span>
          </label>
        </div>
      </div>

      <div class="pp-expiry">
        <p class="pp-expiry__legend">积分有效期</p>
        <div
          class="pp-segmented"
          role="radiogroup"
          aria-label="积分有效期规则"
          data-test="expiry-mode"
        >
          <label
            v-for="option in expiryOptions"
            :key="option.value"
            class="pp-segmented__option"
            :class="{ 'is-active': expiryMode === option.value }"
          >
            <input
              type="radio"
              :value="option.value"
              v-model="expiryMode"
              :data-test="`expiry-${option.slug}`"
              @change="clearFormError"
            />
            <span>{{ option.label }}</span>
          </label>
        </div>
      </div>

      <div class="pp-form__actions">
        <button
          type="submit"
          class="pp-submit"
          data-test="points-policy-submit"
          :disabled="store.pointsPolicyActionLoading || policyVersion === null"
        >
          <Check :size="16" aria-hidden="true" />
          {{ store.pointsPolicyActionLoading ? '正在保存' : '保存规则' }}
        </button>
      </div>
    </form>

    <p
      v-if="store.pointsPolicyFormError"
      class="pp-form__error"
      data-test="points-policy-form-error"
      role="alert"
    >
      <ShieldAlert :size="17" aria-hidden="true" />
      <span>{{ store.pointsPolicyFormError }}</span>
      <span
        v-if="store.pointsPolicyFormErrorCode"
        class="pp-form__code ark-data"
        data-test="points-policy-form-error-code"
      >
        {{ store.pointsPolicyFormErrorCode }}
      </span>
    </p>

    <p
      v-if="successMessage"
      class="pp-form__message"
      data-test="points-policy-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ successMessage }}
    </p>
  </section>
</template>

<style scoped>
.admin-points-policy {
  min-width: 0;
  color: var(--ark-paper);
}

.pp-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.pp-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 26px 24px;
}

.pp-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.pp-header__identity > div {
  min-width: 0;
}

.pp-header h1 {
  margin: 0;
  font-size: 2.2rem;
  line-height: 1;
}

.pp-header p {
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.pp-header__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.pp-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.pp-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.15rem;
  line-height: 1.2;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 18px;
  color: var(--ark-muted);
  text-align: center;
}

.pp-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.pp-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.pp-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.pp-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.pp-form {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.pp-form__heading {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.pp-form__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.pp-form__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.pp-form__heading span {
  min-width: 0;
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-scalars {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  padding: 16px 18px 0;
}

.pp-weights {
  min-width: 0;
  padding: 16px 18px 0;
}

.pp-weights__legend,
.pp-expiry__legend {
  margin: 0 0 10px;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-form__grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.pp-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  align-content: start;
}

.pp-field > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-field input {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.84rem;
}

.pp-field input:hover {
  border-color: var(--ark-signal);
}

.pp-field__error {
  color: var(--ark-signal);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-expiry {
  min-width: 0;
  padding: 16px 18px 0;
}

.pp-segmented {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
  max-width: 420px;
}

.pp-segmented__option {
  display: flex;
  min-width: 0;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  cursor: pointer;
}

.pp-segmented__option input {
  margin: 0;
  accent-color: var(--ark-signal);
}

.pp-segmented__option span {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-segmented__option:hover {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.pp-segmented__option.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.pp-form__actions {
  display: flex;
  min-width: 0;
  align-items: flex-end;
  gap: 8px;
  padding: 18px;
}

.pp-form__actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-submit {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.pp-form__error,
.pp-form__message {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 0 18px 16px;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.pp-form__code {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.pp-form__error {
  color: var(--ark-signal);
}

.pp-form__message {
  color: var(--ark-state);
}

.pp-form__error svg,
.pp-form__message svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.admin-points-policy :is(button, input):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .pp-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .pp-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .pp-form__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .pp-header__summary {
    grid-template-columns: minmax(0, 1fr);
  }

  .pp-scalars,
  .pp-form__grid,
  .pp-segmented {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
