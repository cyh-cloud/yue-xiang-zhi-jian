<script setup lang="ts">
import {
  Check,
  Inbox,
  PackageCheck,
  RefreshCw,
  ScanEye,
  ShieldAlert,
  Wallet
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  AdminFulfillmentStatusFilter,
  AdminPointsLedgerEntry,
  AdminRedemption,
  AdminRedemptionDetail,
  AdminRedemptionStatusFilter
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

interface RedemptionFilters {
  user: string
  reward: string
  status: AdminRedemptionStatusFilter
  fulfillment_status: AdminFulfillmentStatusFilter
  created_from: string
  created_to: string
}

const statusOptions: ReadonlyArray<{
  value: AdminRedemptionStatusFilter
  label: string
}> = [
  { value: 'all', label: '全部兑换' },
  { value: 'pending', label: '待发放' },
  { value: 'issued', label: '已发放' },
  { value: 'verified', label: '已核销' },
  { value: 'canceled', label: '已取消' }
]

const fulfillmentOptions: ReadonlyArray<{
  value: AdminFulfillmentStatusFilter
  label: string
}> = [
  { value: 'all', label: '全部履约' },
  { value: 'pending', label: '待发放' },
  { value: 'issued', label: '已发放' },
  { value: 'verified', label: '已核销' },
  { value: 'canceled', label: '已取消' }
]

const statusLabels: Record<string, string> = {
  all: '全部',
  pending: '待发放',
  issued: '已发放',
  verified: '已核销',
  canceled: '已取消'
}

const roleLabels: Record<string, string> = {
  student: '学员',
  teacher: '教师',
  enterprise: '企业账户',
  government: '政府账户',
  admin: '普通管理员',
  super_admin: '超级管理员'
}

const ledgerTypeLabels: Record<string, string> = {
  award: '发放',
  spend: '兑换扣减',
  refund: '回退',
  expire: '过期'
}

const store = useAdminConsoleStore()
const filters = ref<RedemptionFilters>({
  user: '',
  reward: '',
  status: 'all',
  fulfillment_status: 'all',
  created_from: '',
  created_to: ''
})
const detailMessage = ref('')
const requestedRedemptionId = ref<number | null>(null)

let filterTimer: ReturnType<typeof setTimeout> | undefined

const ledgerTotal = computed(() => store.redemptionDetail?.points_ledger.length ?? 0)

function statusLabel(status: string | null): string {
  if (status === null) return '未开始'
  return statusLabels[status] ?? status
}

function roleLabel(role: string): string {
  return roleLabels[role] ?? role
}

function ledgerTypeLabel(entry: AdminPointsLedgerEntry): string {
  return ledgerTypeLabels[entry.transaction_type] ?? entry.transaction_type
}

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

function reloadRedemptions(): void {
  void store.loadRedemptions({
    user: filters.value.user.trim(),
    reward: filters.value.reward.trim(),
    status: filters.value.status,
    fulfillment_status: filters.value.fulfillment_status,
    created_from: filters.value.created_from,
    created_to: filters.value.created_to
  })
}

function scheduleRedemptionReload(): void {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
  filterTimer = setTimeout(reloadRedemptions, 240)
}

watch(() => filters.value.status, reloadRedemptions)

watch(() => filters.value.fulfillment_status, reloadRedemptions)

watch(() => filters.value.created_from, reloadRedemptions)

watch(() => filters.value.created_to, reloadRedemptions)

watch(
  () => [filters.value.user, filters.value.reward],
  scheduleRedemptionReload
)

async function loadDetail(redemptionId: number): Promise<void> {
  detailMessage.value = ''
  store.clearRedemptionDetailError()
  requestedRedemptionId.value = redemptionId
  const done = await store.loadRedemptionDetail(redemptionId)
  if (done) {
    detailMessage.value = `已载入兑换 #${redemptionId} 的完整上下文`
  }
}

async function openDetail(redemption: AdminRedemption): Promise<void> {
  await loadDetail(redemption.id)
}

function retryDetail(): void {
  if (requestedRedemptionId.value === null) return
  void loadDetail(requestedRedemptionId.value)
}

function closeDetail(): void {
  store.clearRedemptionDetail()
  detailMessage.value = ''
}

function snapshotEntries(detail: AdminRedemptionDetail): Array<[string, string]> {
  const snapshot = detail.reward.snapshot ?? {}
  return Object.entries(snapshot).map(([key, value]) => [
    key,
    typeof value === 'string' ? value : JSON.stringify(value)
  ])
}

onMounted(reloadRedemptions)

onBeforeUnmount(() => {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
})
</script>

<template>
  <section class="admin-redemptions" data-test="admin-redemptions">
    <header class="rd-header">
      <div class="rd-header__identity">
        <PackageCheck :size="26" aria-hidden="true" />
        <div>
          <h1>兑换履约</h1>
          <p>兑换记录、履约状态、学员身份与积分流水的查询入口。</p>
        </div>
      </div>
      <dl class="rd-header__summary">
        <div>
          <dt>兑换记录</dt>
          <dd class="ark-data" data-test="redemption-total">{{ store.redemptions.length }}</dd>
        </div>
        <div>
          <dt>待发放</dt>
          <dd class="ark-data" data-test="redemption-pending-count">
            {{ store.redemptions.filter(item => item.status === 'pending').length }}
          </dd>
        </div>
      </dl>
    </header>

    <p
      v-if="detailMessage"
      class="rd-message"
      data-test="redemption-detail-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ detailMessage }}
    </p>

    <section class="rd-filters" aria-label="兑换记录筛选">
      <div
        class="rd-filter-group"
        role="group"
        aria-label="按兑换状态筛选"
        data-test="redemption-status-filter"
      >
        <button
          v-for="option in statusOptions"
          :key="option.value"
          type="button"
          :data-test="`redemption-filter-${option.value}`"
          :class="{ 'is-active': filters.status === option.value }"
          :aria-pressed="filters.status === option.value"
          @click="filters.status = option.value"
        >
          <span>{{ option.label }}</span>
        </button>
      </div>
      <div
        class="rd-filter-group"
        role="group"
        aria-label="按履约状态筛选"
        data-test="redemption-fulfillment-filter"
      >
        <button
          v-for="option in fulfillmentOptions"
          :key="option.value"
          type="button"
          :data-test="`redemption-fulfillment-${option.value}`"
          :class="{ 'is-active': filters.fulfillment_status === option.value }"
          :aria-pressed="filters.fulfillment_status === option.value"
          @click="filters.fulfillment_status = option.value"
        >
          <span>{{ option.label }}</span>
        </button>
      </div>
      <div class="rd-search">
        <label class="rd-field">
          <span>学员</span>
          <input
            v-model="filters.user"
            type="search"
            data-test="redemption-user"
            placeholder="用户 ID 或姓名"
            aria-label="按学员筛选兑换记录"
          />
        </label>
        <label class="rd-field">
          <span>奖品</span>
          <input
            v-model="filters.reward"
            type="search"
            data-test="redemption-reward"
            placeholder="奖品 ID 或名称"
            aria-label="按奖品筛选兑换记录"
          />
        </label>
        <label class="rd-field">
          <span>开始日期</span>
          <input
            v-model="filters.created_from"
            type="date"
            data-test="redemption-from"
            aria-label="按开始日期筛选兑换记录"
          />
        </label>
        <label class="rd-field">
          <span>结束日期</span>
          <input
            v-model="filters.created_to"
            type="date"
            data-test="redemption-to"
            aria-label="按结束日期筛选兑换记录"
          />
        </label>
      </div>
    </section>

    <div
      v-if="store.redemptionsError"
      class="rd-error"
      data-test="redemption-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.redemptionsError }}</span>
      <button
        type="button"
        data-test="redemption-retry"
        :disabled="store.redemptionsLoading"
        @click="reloadRedemptions"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="rd-registry" aria-labelledby="rd-registry-title">
      <header class="rd-registry__heading">
        <h2 id="rd-registry-title">兑换记录</h2>
        <span class="ark-data">{{ store.redemptions.length }} 条</span>
      </header>

      <div
        v-if="store.redemptionsLoading && store.redemptions.length === 0"
        class="rd-state"
        data-test="redemption-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载兑换记录
      </div>

      <div
        v-else-if="store.redemptions.length === 0"
        class="rd-state rd-state--empty"
        data-test="redemption-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无符合条件的兑换记录</span>
      </div>

      <div v-else class="rd-table-wrap">
        <table class="rd-table" data-test="redemption-table">
          <thead>
            <tr>
              <th scope="col">兑换 ID</th>
              <th scope="col">学员</th>
              <th scope="col">奖品</th>
              <th scope="col">积分成本</th>
              <th scope="col">兑换状态</th>
              <th scope="col">履约状态</th>
              <th scope="col">创建时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in store.redemptions"
              :key="item.id"
              data-test="redemption-row"
              :data-redemption-id="item.id"
            >
              <td data-label="兑换 ID">
                <span class="ark-data">#{{ item.id }}</span>
              </td>
              <td data-label="学员">
                <span class="rd-name">{{ item.user.name }}</span>
                <span class="ark-data rd-sub">#{{ item.user.id }}</span>
              </td>
              <td data-label="奖品">
                <span class="rd-name">{{ item.reward.name }}</span>
                <span class="ark-data rd-sub">{{ item.reward.reward_id }}</span>
              </td>
              <td data-label="积分成本">
                <span class="ark-data">{{ item.points_cost }}</span>
              </td>
              <td data-label="兑换状态">
                <span class="rd-status" :class="`is-${item.status}`" data-test="redemption-status">
                  {{ statusLabel(item.status) }}
                </span>
              </td>
              <td data-label="履约状态">
                <span class="rd-status" :class="`is-${item.fulfillment_status}`">
                  {{ statusLabel(item.fulfillment_status) }}
                </span>
              </td>
              <td data-label="创建时间">
                <time class="ark-data" :datetime="item.created_at ?? undefined">
                  {{ formatTime(item.created_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div class="rd-actions">
                  <button
                    type="button"
                    :aria-label="`查看兑换详情：#${item.id}`"
                    :title="`查看兑换详情：#${item.id}`"
                    data-test="redemption-detail"
                    @click="openDetail(item)"
                  >
                    <ScanEye :size="16" aria-hidden="true" />
                    详情
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section
      v-if="store.redemptionDetailLoading && store.redemptionDetail === null"
      class="rd-detail"
      aria-labelledby="rd-detail-title"
      data-test="redemption-detail-panel"
    >
      <header class="rd-detail__heading">
        <ScanEye :size="20" aria-hidden="true" />
        <h2 id="rd-detail-title">兑换详情</h2>
      </header>
      <div class="rd-state" data-test="redemption-detail-loading" role="status">
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载兑换详情
      </div>
    </section>

    <div
      v-else-if="store.redemptionDetailError"
      class="rd-error"
      data-test="redemption-detail-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.redemptionDetailError }}</span>
      <button
        type="button"
        data-test="redemption-detail-retry"
        :disabled="store.redemptionDetailLoading"
        @click="retryDetail"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section
      v-else-if="store.redemptionDetail"
      class="rd-detail"
      aria-labelledby="rd-detail-title"
      data-test="redemption-detail-panel"
    >
      <header class="rd-detail__heading">
        <ScanEye :size="20" aria-hidden="true" />
        <h2 id="rd-detail-title">兑换详情</h2>
        <span class="ark-data">#{{ store.redemptionDetail.id }}</span>
        <button type="button" data-test="redemption-detail-close" @click="closeDetail">
          关闭
        </button>
      </header>

      <div class="rd-detail__grid">
        <section class="rd-block">
          <header class="rd-block__heading">
            <h3>兑换记录</h3>
          </header>
          <dl class="rd-block__grid">
          <div>
            <dt>请求 ID</dt>
            <dd class="ark-data">{{ store.redemptionDetail.request_id }}</dd>
          </div>
          <div>
            <dt>兑换状态</dt>
            <dd>{{ statusLabel(store.redemptionDetail.status) }}</dd>
          </div>
          <div>
            <dt>积分成本</dt>
            <dd class="ark-data">{{ store.redemptionDetail.points_cost }}</dd>
          </div>
          <div>
            <dt>已回退积分</dt>
            <dd class="ark-data">{{ store.redemptionDetail.restored_points }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd class="ark-data">{{ formatTime(store.redemptionDetail.created_at) }}</dd>
          </div>
          <div>
            <dt>取消时间</dt>
            <dd class="ark-data">{{ formatTime(store.redemptionDetail.canceled_at) }}</dd>
          </div>
          </dl>
        </section>

        <section class="rd-block">
          <header class="rd-block__heading">
            <h3>奖品快照</h3>
          </header>
          <dl class="rd-block__grid">
          <div>
            <dt>奖品 ID</dt>
            <dd class="ark-data">{{ store.redemptionDetail.reward.reward_id }}</dd>
          </div>
          <div>
            <dt>奖品名称</dt>
            <dd>{{ store.redemptionDetail.reward.name }}</dd>
          </div>
          <div>
            <dt>兑换时积分</dt>
            <dd class="ark-data">{{ store.redemptionDetail.reward.points_cost }}</dd>
          </div>
          <template v-if="snapshotEntries(store.redemptionDetail).length > 0">
            <div v-for="[key, value] in snapshotEntries(store.redemptionDetail)" :key="key">
              <dt>快照字段 {{ key }}</dt>
              <dd class="ark-data">{{ value }}</dd>
            </div>
          </template>
          <div v-else>
            <dt>快照字段</dt>
            <dd>兑换时未记录额外快照</dd>
          </div>
          </dl>
        </section>

        <section class="rd-block">
          <header class="rd-block__heading">
            <h3>库存预留</h3>
          </header>
          <dl class="rd-block__grid">
          <template v-if="store.redemptionDetail.stock_reservation">
            <div>
              <dt>预留单号</dt>
              <dd class="ark-data">{{ store.redemptionDetail.stock_reservation.reservation_id }}</dd>
            </div>
            <div>
              <dt>预留状态</dt>
              <dd>{{ statusLabel(store.redemptionDetail.stock_reservation.status) }}</dd>
            </div>
            <div>
              <dt>预留数量</dt>
              <dd class="ark-data">{{ store.redemptionDetail.stock_reservation.quantity }}</dd>
            </div>
            <div>
              <dt>释放时间</dt>
              <dd class="ark-data">
                {{ formatTime(store.redemptionDetail.stock_reservation.released_at) }}
              </dd>
            </div>
          </template>
          <div v-else>
            <dt>预留状态</dt>
            <dd>无库存预留记录</dd>
          </div>
          </dl>
        </section>

        <section class="rd-block">
          <header class="rd-block__heading">
            <h3>履约单</h3>
          </header>
          <dl class="rd-block__grid">
          <template v-if="store.redemptionDetail.fulfillment">
            <div>
              <dt>履约 ID</dt>
              <dd class="ark-data">#{{ store.redemptionDetail.fulfillment.id }}</dd>
            </div>
            <div>
              <dt>履约状态</dt>
              <dd>{{ statusLabel(store.redemptionDetail.fulfillment.status) }}</dd>
            </div>
            <div>
              <dt>发放时间</dt>
              <dd class="ark-data">{{ formatTime(store.redemptionDetail.fulfillment.issued_at) }}</dd>
            </div>
            <div>
              <dt>核销时间</dt>
              <dd class="ark-data">{{ formatTime(store.redemptionDetail.fulfillment.verified_at) }}</dd>
            </div>
            <div>
              <dt>取消时间</dt>
              <dd class="ark-data">{{ formatTime(store.redemptionDetail.fulfillment.canceled_at) }}</dd>
            </div>
          </template>
          <div v-else>
            <dt>履约状态</dt>
            <dd>尚未生成履约单</dd>
          </div>
          </dl>
        </section>

        <section class="rd-block rd-block--user">
          <header class="rd-block__heading">
            <h3>学员身份与联系方式</h3>
          </header>
          <dl class="rd-block__grid">
          <div>
            <dt>用户 ID</dt>
            <dd class="ark-data">#{{ store.redemptionDetail.user.id }}</dd>
          </div>
          <div>
            <dt>用户名</dt>
            <dd class="ark-data">{{ store.redemptionDetail.user.username }}</dd>
          </div>
          <div>
            <dt>姓名</dt>
            <dd>{{ store.redemptionDetail.user.name }}</dd>
          </div>
          <div>
            <dt>身份</dt>
            <dd>{{ roleLabel(store.redemptionDetail.user.role) }}</dd>
          </div>
          <div>
            <dt>联系方式</dt>
            <dd data-test="redemption-user-contact">{{ store.redemptionDetail.user.contact }}</dd>
          </div>
          </dl>
        </section>
      </div>

      <section class="rd-ledger" aria-labelledby="rd-ledger-title">
        <header class="rd-ledger__heading">
          <Wallet :size="20" aria-hidden="true" />
          <h3 id="rd-ledger-title">积分流水</h3>
          <span class="ark-data">{{ ledgerTotal }} 条</span>
        </header>

        <div
          v-if="ledgerTotal === 0"
          class="rd-state rd-state--empty"
          data-test="redemption-ledger-empty"
        >
          <Inbox :size="24" aria-hidden="true" />
          <span>该学员暂无积分流水</span>
        </div>

        <div v-else class="rd-table-wrap">
          <table class="rd-table rd-table--ledger" data-test="redemption-ledger-table">
            <thead>
              <tr>
                <th scope="col">交易类型</th>
                <th scope="col">来源模块</th>
                <th scope="col">来源事件</th>
                <th scope="col">金额</th>
                <th scope="col">余额影响</th>
                <th scope="col">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in store.redemptionDetail.points_ledger"
                :key="entry.id"
                data-test="redemption-ledger-row"
              >
                <td data-label="交易类型">{{ ledgerTypeLabel(entry) }}</td>
                <td data-label="来源模块">{{ entry.source_module }}</td>
                <td data-label="来源事件">
                  <span class="ark-data">{{ entry.source_event_id }}</span>
                </td>
                <td data-label="金额">
                  <span class="ark-data" :class="entry.delta < 0 ? 'is-negative' : 'is-positive'">
                    {{ entry.delta > 0 ? '+' : '' }}{{ entry.delta }}
                  </span>
                </td>
                <td data-label="余额影响">
                  <span class="ark-data">{{ entry.balance_after }}</span>
                </td>
                <td data-label="时间">
                  <time class="ark-data" :datetime="entry.created_at">
                    {{ formatTime(entry.created_at) }}
                  </time>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.admin-redemptions {
  min-width: 0;
  color: var(--ark-paper);
}

.rd-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rd-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 26px 24px;
}

.rd-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.rd-header__identity > div {
  min-width: 0;
}

.rd-header h1 {
  margin: 0;
  font-size: 2.2rem;
  line-height: 1;
}

.rd-header p {
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rd-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.rd-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.rd-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rd-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.9rem;
  line-height: 1;
}

.rd-message,
.rd-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rd-message {
  color: var(--ark-state);
}

.rd-message svg,
.rd-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.rd-message,
.rd-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rd-error button {
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

.rd-filters {
  min-width: 0;
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rd-filter-group {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
}

.rd-filter-group + .rd-filter-group {
  margin-top: 6px;
}

.rd-filter-group button {
  display: flex;
  min-width: 0;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rd-filter-group button:hover,
.rd-filter-group button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.rd-filter-group button.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rd-search {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin-top: 12px;
}

.rd-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  align-content: start;
}

.rd-field > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rd-field input {
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

.rd-field input:hover {
  border-color: var(--ark-signal);
}

.rd-registry,
.rd-detail {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rd-registry__heading,
.rd-detail__heading {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.rd-registry__heading h2,
.rd-detail__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.rd-detail__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.rd-registry__heading span,
.rd-detail__heading span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.rd-detail__heading button {
  display: inline-flex;
  min-height: 36px;
  flex: 0 0 auto;
  align-items: center;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.78rem;
}

.rd-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.rd-state--empty {
  flex-direction: column;
}

.rd-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.rd-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.rd-table th,
.rd-table td {
  min-width: 0;
  padding: 13px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.rd-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
}

.rd-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rd-table time {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.rd-table th:nth-child(1) {
  width: 8%;
}

.rd-table th:nth-child(2) {
  width: 17%;
}

.rd-table th:nth-child(3) {
  width: 18%;
}

.rd-table th:nth-child(4) {
  width: 8%;
}

.rd-table th:nth-child(5),
.rd-table th:nth-child(6) {
  width: 9%;
}

.rd-table th:nth-child(7) {
  width: 13%;
}

.rd-table th:nth-child(8) {
  width: 18%;
}

.rd-table--ledger th:nth-child(1) {
  width: 13%;
}

.rd-table--ledger th:nth-child(2) {
  width: 14%;
}

.rd-table--ledger th:nth-child(3) {
  width: 27%;
}

.rd-table--ledger th:nth-child(4) {
  width: 10%;
}

.rd-table--ledger th:nth-child(5) {
  width: 11%;
}

.rd-table--ledger th:nth-child(6) {
  width: 25%;
}

.rd-table tbody tr:last-child td {
  border-bottom: 0;
}

.rd-name {
  display: block;
  font-weight: 500;
}

.rd-sub {
  display: block;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.rd-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rd-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.rd-status.is-pending {
  color: var(--ark-signal);
}

.rd-status.is-canceled {
  color: var(--ark-muted);
}

.rd-status.is-issued,
.rd-status.is-verified {
  color: var(--ark-state);
}

.rd-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  min-width: 0;
}

.rd-actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.78rem;
}

.rd-actions button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rd-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.rd-block {
  display: grid;
  gap: 1px;
  min-width: 0;
  margin: 0;
  background: var(--ark-line);
}

.rd-block__grid {
  display: grid;
  gap: 1px;
  min-width: 0;
  margin: 0;
  background: var(--ark-line);
}

.rd-block__heading {
  display: flex;
  min-width: 0;
  min-height: 48px;
  align-items: center;
  padding: 10px 18px;
  background: var(--ark-surface-1);
}

.rd-block__heading h3 {
  margin: 0;
  font-size: 0.95rem;
}

.rd-block__grid > div {
  display: grid;
  grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
  min-width: 0;
  padding: 12px 18px;
  background: var(--ark-surface-0);
}

.rd-block dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rd-block dd {
  margin: 0;
  min-width: 0;
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rd-ledger {
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
}

.rd-ledger__heading {
  display: flex;
  min-width: 0;
  min-height: 52px;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
}

.rd-ledger__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.rd-ledger__heading h3 {
  margin: 0;
  font-size: 0.95rem;
}

.rd-ledger__heading span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.is-positive {
  color: var(--ark-state);
}

.is-negative {
  color: var(--ark-signal);
}

.admin-redemptions :is(button, input):focus-visible {
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

@media (max-width: 1120px) {
  .rd-table-wrap {
    overflow-x: visible;
  }

  .rd-table,
  .rd-table tbody {
    display: block;
  }

  .rd-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .rd-table tbody {
    display: grid;
    gap: 1px;
    background: var(--ark-line);
  }

  .rd-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .rd-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .rd-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }

  .rd-table td:last-child {
    border-bottom: 0;
  }
}

@media (max-width: 900px) {
  .rd-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .rd-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .rd-filter-group {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .rd-search {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rd-detail__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 560px) {
  .rd-filter-group {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rd-search {
    grid-template-columns: minmax(0, 1fr);
  }

  .rd-header__summary {
    grid-template-columns: minmax(0, 1fr);
  }

  .rd-block__grid > div {
    grid-template-columns: minmax(0, 1fr);
  }

  .rd-table td {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
