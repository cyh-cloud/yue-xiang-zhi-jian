<script setup lang="ts">
import {
  CalendarClock,
  Coins,
  History,
  RefreshCw
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { useHandcraftPointsStore } from '@/stores/handcraftPoints'

const pointsStore = useHandcraftPointsStore()
const initialLoading = ref(true)
const dailyCapNoticeVisible = ref(false)
const DAILY_CAP_NOTICE_PREFIX = 'handcraft-points-daily-cap'

const orderedLedger = computed(() =>
  [...pointsStore.ledger].sort((left, right) => {
    const leftTime = Date.parse(left.created_at)
    const rightTime = Date.parse(right.created_at)
    if (Number.isFinite(leftTime) && Number.isFinite(rightTime)) {
      return rightTime - leftTime || right.id - left.id
    }
    return right.id - left.id
  })
)

const hasLoaded = computed(
  () => pointsStore.account !== null || pointsStore.ledger.length > 0
)

function entryTypeLabel(transactionType: string): string {
  const labels: Record<string, string> = {
    award: '获取',
    spend: '消耗',
    refund: '回退',
    expire: '过期'
  }
  return labels[transactionType] ?? transactionType
}

function formatDelta(delta: number): string {
  return delta > 0 ? `+${delta}` : String(delta)
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
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

function platformDate(value = new Date()): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
      .formatToParts(value)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day}`
}

function syncDailyCapNotice() {
  dailyCapNoticeVisible.value = false
  const account = pointsStore.account
  if (!account?.daily_limit_reached) {
    return
  }

  const key = [
    DAILY_CAP_NOTICE_PREFIX,
    account.user_id,
    platformDate()
  ].join(':')
  let alreadyShown = false
  try {
    const storage = window.localStorage
    alreadyShown = storage.getItem(key) === '1'
    if (!alreadyShown) {
      storage.setItem(key, '1')
    }
  } catch {
    alreadyShown = false
  }
  dailyCapNoticeVisible.value = !alreadyShown
}

async function loadPoints() {
  initialLoading.value = true
  try {
    const accountLoaded = await pointsStore.loadAccount()
    if (accountLoaded) {
      await pointsStore.loadLedger()
    }
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadPoints()
})

watch(
  () => pointsStore.account,
  syncDailyCapNotice,
  { immediate: true }
)
</script>

<template>
  <main
    class="points-panel"
    data-ark-theme="ark"
    data-ark-depth="maximal"
  >
    <header class="points-hero">
      <div class="points-hero__identity">
        <Coins :size="24" aria-hidden="true" />
        <div>
          <span class="ark-data">POINTS ACCOUNT</span>
          <h1>我的积分</h1>
        </div>
      </div>

      <section class="balance-dossier" aria-label="可用积分">
        <span>可用积分</span>
        <strong class="ark-data" data-test="points-balance">
          {{ pointsStore.account?.balance ?? '--' }}
          <small>积分</small>
        </strong>
        <time
          v-if="pointsStore.account?.updated_at"
          class="ark-data"
          :datetime="pointsStore.account.updated_at"
        >
          更新于 {{ formatTimestamp(pointsStore.account.updated_at) }}
        </time>
      </section>
    </header>

    <aside
      v-if="dailyCapNoticeVisible"
      class="daily-cap-notice"
      data-test="daily-cap-notice"
    >
      <CalendarClock :size="18" aria-hidden="true" />
      <p>今日积分获取已达上限，学习进度将继续累计。</p>
    </aside>

    <div
      v-if="initialLoading || (pointsStore.loading && !hasLoaded)"
      class="panel-status"
      data-test="points-loading"
      role="status"
    >
      <RefreshCw class="spinning" :size="20" aria-hidden="true" />
      正在加载积分
    </div>

    <div
      v-if="pointsStore.error"
      class="panel-error"
      data-test="points-error"
      role="alert"
    >
      <span>{{ pointsStore.error }}</span>
      <button type="button" @click="loadPoints">
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="ledger-section" aria-labelledby="points-ledger-title">
      <header class="section-heading">
        <div>
          <span class="ark-data">TRANSACTION LEDGER</span>
          <h2 id="points-ledger-title">积分流水</h2>
        </div>
        <span class="ark-data">{{ orderedLedger.length }} 条</span>
      </header>

      <p
        v-if="
          !pointsStore.loading &&
          !pointsStore.error &&
          orderedLedger.length === 0
        "
        class="panel-empty"
        data-test="points-empty"
      >
        暂无积分流水
      </p>

      <ol v-else-if="orderedLedger.length" class="ledger-list">
        <li
          v-for="entry in orderedLedger"
          :key="entry.id"
          class="ledger-entry"
          data-test="points-ledger-entry"
          :data-entry-id="entry.id"
        >
          <div class="ledger-entry__marker" aria-hidden="true">
            <History :size="17" />
          </div>
          <div class="ledger-entry__body">
            <header>
              <strong>{{ entryTypeLabel(entry.transaction_type) }}</strong>
              <time class="ark-data" :datetime="entry.created_at">
                {{ formatTimestamp(entry.created_at) }}
              </time>
            </header>
            <p class="ledger-entry__detail">
              {{ entry.source_module }} · {{ entry.source_event_id }}
            </p>
            <div class="ledger-entry__metrics">
              <span class="ark-data">
                余额 {{ entry.balance_after }}
              </span>
              <strong
                class="ark-data"
                :class="{
                  'is-positive': entry.delta > 0,
                  'is-negative': entry.delta < 0
                }"
              >
                {{ formatDelta(entry.delta) }}
              </strong>
            </div>
          </div>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.points-panel {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color: var(--ark-paper);
}

.points-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.72fr);
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.points-hero__identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 16px;
  padding: 28px 26px;
}

.points-hero__identity > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.points-hero__identity > div {
  min-width: 0;
}

.points-hero__identity span,
.section-heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.points-hero__identity h1 {
  margin: 4px 0 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.balance-dossier {
  display: grid;
  min-width: 0;
  align-content: center;
  gap: 5px;
  padding: 20px 26px;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.balance-dossier > span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.balance-dossier > strong {
  color: var(--ark-signal);
  font-size: 2.7rem;
  line-height: 1;
  overflow-wrap: anywhere;
}

.balance-dossier > strong small {
  color: var(--ark-paper);
  font-size: 0.78rem;
  font-weight: 500;
}

.balance-dossier time {
  color: var(--ark-muted);
  font-size: 0.72rem;
  overflow-wrap: anywhere;
}

.daily-cap-notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
}

.daily-cap-notice svg {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--ark-signal);
}

.daily-cap-notice p {
  min-width: 0;
  margin: 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.panel-status,
.panel-empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 18px 0 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.panel-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.panel-error > span {
  min-width: 0;
  overflow-wrap: anywhere;
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

.ledger-section {
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

.ledger-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.ledger-entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  min-width: 0;
  padding: 17px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.ledger-entry:last-child {
  border-bottom: 0;
}

.ledger-entry__marker {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.ledger-entry__body {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.ledger-entry__body header,
.ledger-entry__metrics {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ledger-entry__body header strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.ledger-entry__body time {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.ledger-entry__detail {
  min-width: 0;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.ledger-entry__metrics {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.ledger-entry__metrics strong {
  color: var(--ark-muted);
}

.ledger-entry__metrics strong.is-positive {
  color: var(--ark-state);
}

.ledger-entry__metrics strong.is-negative {
  color: var(--ark-signal);
}

.points-panel :is(button, a):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.panel-error button:hover {
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
  .points-panel {
    padding: 28px 14px 48px;
  }

  .points-hero {
    grid-template-columns: minmax(0, 1fr);
  }

  .points-hero__identity,
  .balance-dossier {
    padding: 20px 16px;
  }

  .balance-dossier {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .points-hero__identity h1 {
    font-size: 2.15rem;
  }

  .panel-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .ledger-entry {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px 14px;
  }

  .ledger-entry__marker {
    display: none;
  }

  .ledger-entry__body header {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .ledger-entry__body time {
    flex: initial;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
