<script setup lang="ts">
import {
  Ban,
  CheckCircle2,
  Clock3,
  Gift,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
  XCircle
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type {
  HandcraftFulfillmentStatus,
  HandcraftRedemptionHistory,
  HandcraftReward
} from '@/api/types'
import { useHandcraftRewardsStore } from '@/stores/handcraftRewards'

const rewardsStore = useHandcraftRewardsStore()
const selectedRewardId = ref<string | null>(null)
const actionMessage = ref('')
const initialLoading = ref(true)

const selectedReward = computed(
  () =>
    rewardsStore.rewards.find(
      reward => reward.reward_id === selectedRewardId.value
    ) ?? null
)

const statusLabels: Record<HandcraftFulfillmentStatus, string> = {
  pending: '待发放',
  issued: '已发放',
  verified: '已核销',
  canceled: '已取消'
}

function rewardStateLabel(reward: HandcraftReward): string {
  if (!reward.source_available) {
    return reward.unavailable_reason || '来源不可用'
  }
  if (!reward.is_online) {
    return reward.unavailable_reason || '已下架'
  }
  if (reward.stock <= 0) {
    return '已抢完'
  }
  if (!reward.affordable && reward.unavailable_reason) {
    return reward.unavailable_reason
  }
  return '可兑换'
}

function rewardActionLabel(reward: HandcraftReward): string {
  if (reward.can_redeem) {
    return '兑换奖品'
  }
  if (reward.stock <= 0) {
    return '已抢完'
  }
  if (!reward.is_online) {
    return '已下架'
  }
  return '暂不可兑换'
}

function statusLabel(status: HandcraftFulfillmentStatus): string {
  return statusLabels[status]
}

function createRequestId(rewardId: string): string {
  const uniquePart =
    typeof globalThis.crypto?.randomUUID === 'function'
      ? globalThis.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `${rewardId}:${uniquePart}`
}

function selectReward(reward: HandcraftReward) {
  if (!reward.can_redeem || rewardsStore.redeeming) {
    return
  }
  actionMessage.value = ''
  rewardsStore.clearError()
  selectedRewardId.value = reward.reward_id
}

function cancelSelection() {
  selectedRewardId.value = null
}

async function confirmRedemption() {
  const reward = selectedReward.value
  if (!reward || !reward.can_redeem || rewardsStore.redeeming) {
    return
  }

  const redeemed = await rewardsStore.redeem(
    reward.reward_id,
    createRequestId(reward.reward_id)
  )
  selectedRewardId.value = null

  if (!redeemed) {
    actionMessage.value = ''
    return
  }

  actionMessage.value = '兑换成功，已生成待发放履约单'
  const rewardsLoaded = await rewardsStore.loadRewards()
  if (rewardsLoaded) {
    await rewardsStore.loadRedemptions()
  }
}

async function cancelPending(
  record: HandcraftRedemptionHistory
) {
  if (record.status !== 'pending' || rewardsStore.canceling) {
    return
  }
  actionMessage.value = ''
  const canceled = await rewardsStore.cancelRedemption(
    record.redemption.id
  )
  if (canceled) {
    actionMessage.value = '兑换已取消，积分已回退'
  }
}

async function verifyIssued(
  record: HandcraftRedemptionHistory
) {
  if (record.status !== 'issued' || rewardsStore.verifying) {
    return
  }
  actionMessage.value = ''
  const verified = await rewardsStore.verifyRedemption(
    record.redemption.id
  )
  if (verified) {
    actionMessage.value = '确认收货成功，履约已核销'
  }
}

async function retryHistory() {
  actionMessage.value = ''
  await rewardsStore.loadRedemptions()
}

async function loadRewards() {
  try {
    const rewardsLoaded = await rewardsStore.loadRewards()
    if (rewardsLoaded) {
      await rewardsStore.loadRedemptions()
    }
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadRewards()
})
</script>

<template>
  <main
    class="rewards-panel"
    data-ark-theme="ark"
    data-ark-depth="maximal"
  >
    <header class="rewards-intro">
      <div>
        <Gift :size="24" aria-hidden="true" />
        <div>
          <span class="ark-data">REWARD EXCHANGE</span>
          <h1>奖品兑换</h1>
        </div>
      </div>
    </header>

    <div
      v-if="actionMessage"
      class="action-message"
      data-test="redemption-success"
      role="status"
    >
      <CheckCircle2 :size="18" aria-hidden="true" />
      <span>{{ actionMessage }}</span>
    </div>

    <div
      v-if="rewardsStore.error"
      class="panel-error"
      data-test="rewards-action-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ rewardsStore.error }}</span>
    </div>

    <section class="reward-section" aria-labelledby="reward-list-title">
      <header class="section-heading">
        <div>
          <span class="ark-data">PUBLISHED REWARDS</span>
          <h2 id="reward-list-title">奖品目录</h2>
        </div>
        <span class="ark-data">{{ rewardsStore.rewards.length }} 项</span>
      </header>

      <div
        v-if="
          initialLoading ||
          (rewardsStore.loading && rewardsStore.rewards.length === 0)
        "
        class="panel-status"
        data-test="rewards-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载奖品
      </div>

      <div
        v-else-if="rewardsStore.catalogError"
        class="panel-error"
        data-test="rewards-error"
        role="alert"
      >
        <span>{{ rewardsStore.catalogError }}</span>
        <button type="button" @click="loadRewards">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <p
        v-else-if="rewardsStore.rewards.length === 0"
        class="panel-empty"
        data-test="rewards-empty"
      >
        暂无可兑换奖品
      </p>

      <div v-else class="reward-grid">
        <article
          v-for="reward in rewardsStore.rewards"
          :key="reward.reward_id"
          class="reward-card"
          :class="{
            'is-available': reward.can_redeem,
            'is-unavailable': !reward.can_redeem
          }"
          :data-test="`reward-${reward.reward_id}`"
        >
          <header class="reward-card__head">
            <span class="ark-data">
              REWARD / {{ reward.reward_id }}
            </span>
            <span
              class="reward-card__state"
              data-test="reward-state"
            >
              {{ rewardStateLabel(reward) }}
            </span>
          </header>

          <div class="reward-card__body">
            <div class="reward-card__icon" aria-hidden="true">
              <Gift :size="23" />
            </div>
            <div>
              <h3>{{ reward.name }}</h3>
            </div>
          </div>

          <dl class="reward-card__meta">
            <div>
              <dt>所需积分</dt>
              <dd class="ark-data">{{ reward.points_cost }}</dd>
            </div>
            <div>
              <dt>剩余库存</dt>
              <dd class="ark-data">{{ reward.stock }}</dd>
            </div>
          </dl>

          <div
            v-if="!reward.can_redeem && reward.unavailable_reason"
            class="reward-card__reason"
          >
            <Ban :size="16" aria-hidden="true" />
            <span>{{ reward.unavailable_reason }}</span>
          </div>

          <button
            class="reward-card__action"
            type="button"
            :data-test="`redeem-${reward.reward_id}`"
            :disabled="!reward.can_redeem || rewardsStore.redeeming"
            @click="selectReward(reward)"
          >
            {{ rewardActionLabel(reward) }}
          </button>

          <div
            v-if="selectedRewardId === reward.reward_id"
            class="redeem-confirmation"
            data-test="redeem-confirmation"
          >
            <p>
              确认兑换「{{ reward.name }}」？将扣除
              {{ reward.points_cost }} 积分。
            </p>
            <div>
              <button
                type="button"
                :data-test="`confirm-redeem-${reward.reward_id}`"
                :disabled="rewardsStore.redeeming"
                @click="confirmRedemption"
              >
                <CheckCircle2 :size="16" aria-hidden="true" />
                {{ rewardsStore.redeeming ? '兑换中' : '确认兑换' }}
              </button>
              <button
                type="button"
                :data-test="`cancel-redeem-${reward.reward_id}`"
                :disabled="rewardsStore.redeeming"
                @click="cancelSelection"
              >
                取消
              </button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section
      class="fulfillment-section"
      aria-labelledby="fulfillment-history-title"
    >
      <header class="section-heading">
        <div>
          <span class="ark-data">FULFILLMENT HISTORY</span>
          <h2 id="fulfillment-history-title">兑换记录</h2>
        </div>
        <span class="ark-data">
          {{ rewardsStore.fulfillments.length }} 条
        </span>
      </header>

      <div
        v-if="rewardsStore.historyError"
        class="panel-error fulfillment-error"
        data-test="fulfillment-error"
        role="alert"
      >
        <span>{{ rewardsStore.historyError }}</span>
        <button
          type="button"
          data-test="fulfillment-retry"
          @click="retryHistory"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重试兑换记录
        </button>
      </div>

      <p
        v-else-if="
          !rewardsStore.loading &&
          rewardsStore.fulfillments.length === 0
        "
        class="panel-empty"
        data-test="fulfillment-empty"
      >
        暂无兑换记录
      </p>

      <ol v-else-if="rewardsStore.fulfillments.length" class="fulfillment-list">
        <li
          v-for="record in rewardsStore.fulfillments"
          :key="record.redemption.id"
          class="fulfillment-record"
          data-test="redemption-record"
          :data-redemption-id="record.redemption.id"
        >
          <div class="fulfillment-record__identity">
            <span class="ark-data">
              ORDER {{ record.redemption.id }}
            </span>
            <h3>{{ record.redemption.reward_name }}</h3>
            <p class="ark-data">
              {{ record.redemption.points_cost }} 积分
            </p>
          </div>

          <div class="fulfillment-record__state">
            <Clock3
              v-if="record.status === 'pending'"
              :size="17"
              aria-hidden="true"
            />
            <PackageCheck
              v-else-if="record.status === 'issued'"
              :size="17"
              aria-hidden="true"
            />
            <CheckCircle2
              v-else-if="record.status === 'verified'"
              :size="17"
              aria-hidden="true"
            />
            <XCircle v-else :size="17" aria-hidden="true" />
            <strong
              data-test="redemption-status"
              :class="`is-${record.status}`"
            >
              {{ statusLabel(record.status) }}
            </strong>
          </div>

          <button
            v-if="record.status === 'pending'"
            class="fulfillment-record__cancel"
            type="button"
            :data-test="`cancel-redemption-${record.redemption.id}`"
            :disabled="rewardsStore.canceling"
            @click="cancelPending(record)"
          >
            <XCircle :size="16" aria-hidden="true" />
            {{ rewardsStore.canceling ? '取消中' : '取消兑换' }}
          </button>
          <button
            v-if="record.status === 'issued'"
            class="fulfillment-record__verify"
            type="button"
            :data-test="`verify-redemption-${record.redemption.id}`"
            :disabled="rewardsStore.verifying"
            @click="verifyIssued(record)"
          >
            <CheckCircle2 :size="16" aria-hidden="true" />
            {{ rewardsStore.verifying ? '确认中' : '确认收货' }}
          </button>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.rewards-panel {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color: var(--ark-paper);
}

.rewards-intro {
  display: flex;
  min-width: 0;
  align-items: center;
  padding: 22px 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
}

.rewards-intro > div {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 16px;
}

.rewards-intro svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.rewards-intro > div > div {
  min-width: 0;
}

.rewards-intro span,
.section-heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.rewards-intro h1 {
  margin: 4px 0 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.action-message,
.panel-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.action-message {
  color: var(--ark-state);
}

.action-message svg,
.panel-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.action-message span,
.panel-error > span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.panel-error {
  justify-content: space-between;
  color: var(--ark-paper);
}

.panel-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.reward-section,
.fulfillment-section {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.section-heading {
  display: flex;
  min-height: 66px;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.section-heading > div {
  min-width: 0;
}

.section-heading h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
}

.panel-status,
.panel-empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 0;
  color: var(--ark-muted);
}

.reward-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1px;
  background: var(--ark-line);
}

.reward-card {
  display: grid;
  min-width: 0;
  align-content: start;
  padding: 18px;
  background: var(--ark-surface-0);
}

.reward-card.is-unavailable {
  background: var(--ark-surface-1);
}

.reward-card__head {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.reward-card__head > span:first-child {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.66rem;
  overflow-wrap: anywhere;
}

.reward-card__state {
  flex: 0 1 auto;
  max-width: 100%;
  padding: 3px 7px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  font-size: 0.7rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: right;
  word-break: keep-all;
}

.reward-card.is-available .reward-card__state {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.reward-card__body {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  margin-top: 18px;
}

.reward-card__icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border: 1px solid var(--ark-line);
  color: var(--ark-signal);
}

.reward-card__body > div:last-child {
  min-width: 0;
}

.reward-card h3 {
  margin: 0;
  font-size: 1.18rem;
  line-height: 1.3;
  text-wrap: balance;
  word-break: keep-all;
}

.reward-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin: 18px 0 0;
  background: var(--ark-line);
}

.reward-card__meta div {
  min-width: 0;
  padding: 10px;
  background: var(--ark-surface-1);
}

.reward-card__meta dt {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.reward-card__meta dd {
  margin: 3px 0 0;
  font-size: 0.92rem;
}

.reward-card__reason {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 13px;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.reward-card__reason svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.reward-card__action {
  display: inline-flex;
  width: 100%;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  margin-top: 15px;
  border: 1px solid var(--ark-signal);
  background: transparent;
  color: var(--ark-signal);
}

.reward-card__action:hover:not(:disabled) {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.reward-card__action:disabled {
  border-color: var(--ark-line);
  color: var(--ark-muted);
  opacity: 1;
}

.redeem-confirmation {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.redeem-confirmation p {
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.redeem-confirmation > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 11px;
}

.redeem-confirmation button {
  display: inline-flex;
  flex: 1 1 120px;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.redeem-confirmation button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.fulfillment-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.fulfillment-record {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  min-width: 0;
  align-items: center;
  gap: 18px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.fulfillment-record:last-child {
  border-bottom: 0;
}

.fulfillment-record__identity {
  min-width: 0;
}

.fulfillment-record__identity > span,
.fulfillment-record__identity > p {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.fulfillment-record__identity h3 {
  margin: 4px 0 0;
  font-size: 1rem;
  overflow-wrap: anywhere;
}

.fulfillment-record__identity p {
  margin: 3px 0 0;
}

.fulfillment-record__state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.fulfillment-record__state svg {
  color: var(--ark-muted);
}

.fulfillment-record__state strong {
  font-size: 0.78rem;
}

.fulfillment-record__state strong.is-pending,
.fulfillment-record__state strong.is-issued {
  color: var(--ark-signal);
}

.fulfillment-record__state strong.is-verified {
  color: var(--ark-state);
}

.fulfillment-record__state strong.is-canceled {
  color: var(--ark-muted);
}

.fulfillment-record__cancel,
.fulfillment-record__verify {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.fulfillment-record__verify {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rewards-panel :is(button, a):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.panel-error button:hover,
.fulfillment-record__cancel:hover:not(:disabled),
.fulfillment-record__verify:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px), (orientation: portrait) {
  .rewards-panel {
    padding: 28px 14px 48px;
  }

  .rewards-intro {
    align-items: flex-start;
    flex-direction: column;
    gap: 13px;
  }

  .rewards-intro h1 {
    font-size: 2.15rem;
  }

  .reward-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .panel-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .fulfillment-record {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 10px;
    padding: 16px 14px;
  }

  .fulfillment-record__cancel,
  .fulfillment-record__verify {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
