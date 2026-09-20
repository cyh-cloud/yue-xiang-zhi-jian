<script setup lang="ts">
import {
  BadgeCheck,
  Ban,
  Check,
  Gift,
  Inbox,
  PackageCheck,
  Pencil,
  RefreshCw,
  Send,
  ShieldAlert,
  X
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  AdminFulfillment,
  AdminFulfillmentStatusFilter,
  AdminReward,
  AdminRewardCreatePayload,
  AdminRewardUpdatePayload
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

type FulfillmentAction = 'issue' | 'cancel' | 'verify'

interface FulfillmentFilters {
  user: string
  reward: string
  status: AdminFulfillmentStatusFilter
  created_from: string
  created_to: string
}

const statusOptions: ReadonlyArray<{
  value: AdminFulfillmentStatusFilter
  label: string
}> = [
  { value: 'all', label: '全部状态' },
  { value: 'pending', label: '待发放' },
  { value: 'issued', label: '已发放' },
  { value: 'verified', label: '已核销' },
  { value: 'canceled', label: '已取消' }
]

const statusLabels: Record<AdminFulfillmentStatusFilter, string> = {
  all: '全部状态',
  pending: '待发放',
  issued: '已发放',
  verified: '已核销',
  canceled: '已取消'
}

const actionLabels: Record<
  FulfillmentAction,
  { button: string; title: string; busy: string }
> = {
  issue: { button: '发放奖品', title: '发放', busy: '正在发放' },
  cancel: { button: '取消履约', title: '取消', busy: '正在取消' },
  verify: { button: '核销履约', title: '核销', busy: '正在核销' }
}

const store = useAdminConsoleStore()
const filters = ref<FulfillmentFilters>({
  user: '',
  reward: '',
  status: 'all',
  created_from: '',
  created_to: ''
})
const form = ref({ name: '', points_cost: '', stock: '' })
const editingId = ref<string | null>(null)
const editingVersion = ref<number | null>(null)
const actionMessage = ref('')
const formMessage = ref('')
const onlineCandidate = ref<AdminReward | null>(null)
const actionCandidate = ref<{
  fulfillment: AdminFulfillment
  action: FulfillmentAction
} | null>(null)

let filterTimer: ReturnType<typeof setTimeout> | undefined

const onlineCount = computed(
  () => store.rewards.filter(reward => reward.is_online).length
)

const pendingCount = computed(
  () => store.fulfillments.filter(item => item.status === 'pending').length
)

const canSubmit = computed(() => {
  const points = Number(form.value.points_cost)
  const stock = Number(form.value.stock)
  return (
    form.value.name.trim().length > 0 &&
    String(form.value.points_cost).trim().length > 0 &&
    String(form.value.stock).trim().length > 0 &&
    Number.isInteger(points) &&
    points > 0 &&
    Number.isInteger(stock) &&
    stock >= 0
  )
})

function statusLabel(status: string): string {
  return statusLabels[status as AdminFulfillmentStatusFilter] ?? status
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

function reloadFulfillments(): void {
  void store.loadFulfillments({
    user: filters.value.user.trim(),
    reward: filters.value.reward.trim(),
    status: filters.value.status,
    fulfillment_status: 'all',
    created_from: filters.value.created_from,
    created_to: filters.value.created_to
  })
}

function scheduleFulfillmentReload(): void {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
  filterTimer = setTimeout(reloadFulfillments, 240)
}

watch(
  () => filters.value.status,
  reloadFulfillments
)

watch(
  () => filters.value.created_from,
  reloadFulfillments
)

watch(
  () => filters.value.created_to,
  reloadFulfillments
)

watch(
  () => [filters.value.user, filters.value.reward],
  scheduleFulfillmentReload
)

function resetForm(): void {
  editingId.value = null
  editingVersion.value = null
  form.value = { name: '', points_cost: '', stock: '' }
}

function startEdit(reward: AdminReward): void {
  store.clearRewardFormError()
  formMessage.value = ''
  editingId.value = reward.reward_id
  editingVersion.value = reward.version
  form.value = {
    name: reward.name,
    points_cost: String(reward.points_cost),
    stock: String(reward.stock)
  }
}

async function submitForm(): Promise<void> {
  if (!canSubmit.value) return
  const payload = {
    name: form.value.name.trim(),
    points_cost: Number(form.value.points_cost),
    stock: Number(form.value.stock)
  }
  const wasEditing = editingId.value
  const done =
    wasEditing === null
      ? await store.createReward(payload as AdminRewardCreatePayload)
      : await store.updateReward(wasEditing, {
          ...payload,
          expected_version: editingVersion.value ?? 1
        } satisfies AdminRewardUpdatePayload)
  if (done) {
    formMessage.value =
      wasEditing === null
        ? `已创建奖品「${payload.name}」`
        : `已保存奖品「${payload.name}」`
    resetForm()
  }
}

function openOnlineToggle(reward: AdminReward): void {
  actionMessage.value = ''
  store.clearRewardsError()
  onlineCandidate.value = reward
}

function openAction(
  fulfillment: AdminFulfillment,
  action: FulfillmentAction
): void {
  actionMessage.value = ''
  store.clearFulfillmentsError()
  actionCandidate.value = { fulfillment, action }
}

function closeDialogs(): void {
  onlineCandidate.value = null
  actionCandidate.value = null
}

async function confirmOnlineToggle(): Promise<void> {
  const reward = onlineCandidate.value
  if (reward === null) return
  const online = !reward.is_online
  const done = await store.setRewardOnline(reward.reward_id, reward.version, online)
  if (done) {
    actionMessage.value = `奖品「${reward.name}」已${online ? '上架' : '下架'}`
    closeDialogs()
  }
}

async function confirmAction(): Promise<void> {
  const candidate = actionCandidate.value
  if (candidate === null) return
  const { fulfillment, action } = candidate
  const done =
    action === 'issue'
      ? await store.issueFulfillment(fulfillment.id)
      : action === 'cancel'
        ? await store.cancelFulfillment(fulfillment.id)
        : await store.verifyFulfillment(fulfillment.id)
  if (done) {
    actionMessage.value = `履约 #${fulfillment.id} 已${actionLabels[action].title}`
    closeDialogs()
  }
}

function availableActions(fulfillment: AdminFulfillment): FulfillmentAction[] {
  if (fulfillment.status === 'pending') return ['issue', 'cancel']
  if (fulfillment.status === 'issued') return ['verify']
  return []
}

onMounted(() => {
  void store.loadRewards()
  reloadFulfillments()
})

onBeforeUnmount(() => {
  if (filterTimer) {
    clearTimeout(filterTimer)
  }
})
</script>

<template>
  <section class="admin-rewards" data-test="admin-rewards">
    <header class="rw-header">
      <div class="rw-header__identity">
        <Gift :size="26" aria-hidden="true" />
        <div>
          <h1>奖品管理</h1>
          <p>维护奖品名称、积分成本与库存，并处理待发放的履约单。</p>
        </div>
      </div>
      <dl class="rw-header__summary">
        <div>
          <dt>奖品总数</dt>
          <dd class="ark-data" data-test="reward-total">{{ store.rewards.length }}</dd>
        </div>
        <div>
          <dt>已上架</dt>
          <dd class="ark-data" data-test="reward-online-count">{{ onlineCount }}</dd>
        </div>
        <div>
          <dt>待发放履约</dt>
          <dd class="ark-data" data-test="fulfillment-pending-count">{{ pendingCount }}</dd>
        </div>
      </dl>
    </header>

    <p
      v-if="actionMessage"
      class="rw-message"
      data-test="reward-action-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ actionMessage }}
    </p>

    <div
      v-if="store.rewardsError"
      class="rw-error"
      data-test="reward-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.rewardsError }}</span>
      <button
        type="button"
        data-test="reward-retry"
        :disabled="store.rewardsLoading"
        @click="store.loadRewards()"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="rw-form" aria-labelledby="rw-form-title">
      <header class="rw-form__heading">
        <Pencil :size="20" aria-hidden="true" />
        <h2 id="rw-form-title">{{ editingId === null ? '新建奖品' : '编辑奖品' }}</h2>
        <span>库存不得低于待发放履约已预留数量。</span>
      </header>
      <form class="rw-form__grid" data-test="reward-form" @submit.prevent="submitForm">
        <label class="rw-field">
          <span>奖品名称</span>
          <input
            v-model.trim="form.name"
            type="text"
            data-test="reward-name"
            maxlength="60"
            autocomplete="off"
          />
        </label>
        <label class="rw-field">
          <span>积分成本</span>
          <input
            v-model="form.points_cost"
            type="number"
            min="1"
            step="1"
            data-test="reward-points"
            inputmode="numeric"
          />
        </label>
        <label class="rw-field">
          <span>库存</span>
          <input
            v-model="form.stock"
            type="number"
            min="0"
            step="1"
            data-test="reward-stock"
            inputmode="numeric"
          />
        </label>
        <div class="rw-form__actions">
          <button
            type="submit"
            class="rw-submit"
            data-test="reward-submit"
            :disabled="!canSubmit || store.rewardActionLoading"
          >
            <Check :size="16" aria-hidden="true" />
            {{ store.rewardActionLoading ? '正在保存' : editingId === null ? '创建奖品' : '保存奖品' }}
          </button>
          <button
            v-if="editingId !== null"
            type="button"
            data-test="reward-edit-cancel"
            :disabled="store.rewardActionLoading"
            @click="resetForm"
          >
            取消编辑
          </button>
        </div>
      </form>
      <p
        v-if="store.rewardFormError"
        class="rw-form__error"
        data-test="reward-form-error"
        role="alert"
      >
        <ShieldAlert :size="17" aria-hidden="true" />
        <span>{{ store.rewardFormError }}</span>
      </p>
      <p
        v-if="formMessage"
        class="rw-form__message"
        data-test="reward-form-message"
        role="status"
      >
        <Check :size="17" aria-hidden="true" />
        {{ formMessage }}
      </p>
    </section>

    <section class="rw-registry" aria-labelledby="rw-registry-title">
      <header class="rw-registry__heading">
        <h2 id="rw-registry-title">奖品目录</h2>
        <span class="ark-data">{{ store.rewards.length }} 条</span>
      </header>

      <div
        v-if="store.rewardsLoading && store.rewards.length === 0"
        class="rw-state"
        data-test="reward-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载奖品目录
      </div>

      <div
        v-else-if="store.rewards.length === 0"
        class="rw-state rw-state--empty"
        data-test="reward-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无奖品配置</span>
      </div>

      <div v-else class="rw-table-wrap">
        <table class="rw-table" data-test="reward-table">
          <thead>
            <tr>
              <th scope="col">奖品 ID</th>
              <th scope="col">名称</th>
              <th scope="col">积分成本</th>
              <th scope="col">配置库存</th>
              <th scope="col">已预留</th>
              <th scope="col">可兑换</th>
              <th scope="col">上架状态</th>
              <th scope="col">版本</th>
              <th scope="col">更新时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="reward in store.rewards"
              :key="reward.reward_id"
              data-test="reward-row"
              :data-reward-id="reward.reward_id"
            >
              <td data-label="奖品 ID">
                <span class="ark-data">{{ reward.reward_id }}</span>
              </td>
              <td data-label="名称">
                <span class="rw-name">{{ reward.name }}</span>
              </td>
              <td data-label="积分成本">
                <span class="ark-data">{{ reward.points_cost }}</span>
              </td>
              <td data-label="配置库存">
                <span class="ark-data">{{ reward.stock }}</span>
              </td>
              <td data-label="已预留">
                <span class="ark-data">{{ reward.reserved }}</span>
              </td>
              <td data-label="可兑换">
                <span class="ark-data">{{ reward.available }}</span>
              </td>
              <td data-label="上架状态">
                <span
                  class="rw-status"
                  :class="reward.is_online ? 'is-online' : 'is-offline'"
                  data-test="reward-status"
                >
                  {{ reward.is_online ? '已上架' : '已下架' }}
                </span>
              </td>
              <td data-label="版本">
                <span class="ark-data">{{ reward.version }}</span>
              </td>
              <td data-label="更新时间">
                <time class="ark-data" :datetime="reward.updated_at">
                  {{ formatTime(reward.updated_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div class="rw-actions">
                  <button
                    type="button"
                    :aria-label="`编辑奖品：${reward.name}`"
                    :title="`编辑奖品：${reward.name}`"
                    data-test="reward-edit"
                    :disabled="store.rewardActionLoading"
                    @click="startEdit(reward)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="reward.is_online"
                    :aria-label="`${reward.is_online ? '下架' : '上架'}奖品：${reward.name}`"
                    :title="`${reward.is_online ? '下架' : '上架'}奖品：${reward.name}`"
                    :data-test="`reward-online-${reward.reward_id}`"
                    :disabled="store.rewardActionLoading"
                    @click="openOnlineToggle(reward)"
                  >
                    <Gift :size="16" aria-hidden="true" />
                    {{ reward.is_online ? '下架' : '上架' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div
      v-if="store.fulfillmentsError"
      class="rw-error"
      data-test="fulfillment-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.fulfillmentsError }}</span>
      <button
        type="button"
        data-test="fulfillment-retry"
        :disabled="store.fulfillmentsLoading"
        @click="reloadFulfillments"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="rw-queue" aria-labelledby="rw-queue-title">
      <header class="rw-queue__heading">
        <PackageCheck :size="20" aria-hidden="true" />
        <h2 id="rw-queue-title">履约队列</h2>
        <span class="ark-data">{{ store.fulfillments.length }} 条</span>
      </header>

      <div class="rw-queue__filters">
        <div
          class="rw-status-filter"
          role="group"
          aria-label="按履约状态筛选队列"
          data-test="fulfillment-status-filter"
        >
          <button
            v-for="option in statusOptions"
            :key="option.value"
            type="button"
            :data-test="`fulfillment-filter-${option.value}`"
            :class="{ 'is-active': filters.status === option.value }"
            :aria-pressed="filters.status === option.value"
            @click="filters.status = option.value"
          >
            <span>{{ option.label }}</span>
          </button>
        </div>
        <div class="rw-search">
          <label class="rw-field">
            <span>学员</span>
            <input
              v-model="filters.user"
              type="search"
              data-test="fulfillment-user"
              placeholder="用户 ID 或姓名"
              aria-label="按学员筛选履约队列"
            />
          </label>
          <label class="rw-field">
            <span>奖品</span>
            <input
              v-model="filters.reward"
              type="search"
              data-test="fulfillment-reward"
              placeholder="奖品 ID 或名称"
              aria-label="按奖品筛选履约队列"
            />
          </label>
          <label class="rw-field">
            <span>开始日期</span>
            <input
              v-model="filters.created_from"
              type="date"
              data-test="fulfillment-from"
              aria-label="按开始日期筛选履约队列"
            />
          </label>
          <label class="rw-field">
            <span>结束日期</span>
            <input
              v-model="filters.created_to"
              type="date"
              data-test="fulfillment-to"
              aria-label="按结束日期筛选履约队列"
            />
          </label>
        </div>
      </div>

      <div
        v-if="store.fulfillmentsLoading && store.fulfillments.length === 0"
        class="rw-state"
        data-test="fulfillment-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载履约队列
      </div>

      <div
        v-else-if="store.fulfillments.length === 0"
        class="rw-state rw-state--empty"
        data-test="fulfillment-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无符合条件的履约单</span>
      </div>

      <div v-else class="rw-table-wrap">
        <table class="rw-table rw-table--queue" data-test="fulfillment-table">
          <thead>
            <tr>
              <th scope="col">履约 ID</th>
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
              v-for="item in store.fulfillments"
              :key="item.id"
              data-test="fulfillment-row"
              :data-fulfillment-id="item.id"
            >
              <td data-label="履约 ID">
                <span class="ark-data">#{{ item.id }}</span>
              </td>
              <td data-label="学员">
                <span class="rw-name">{{ item.user.name }}</span>
                <span class="ark-data rw-sub">#{{ item.user.id }}</span>
              </td>
              <td data-label="奖品">
                <span class="rw-name">{{ item.reward.name }}</span>
                <span class="ark-data rw-sub">{{ item.reward.reward_id }}</span>
              </td>
              <td data-label="积分成本">
                <span class="ark-data">{{ item.points_cost }}</span>
              </td>
              <td data-label="兑换状态">
                <span class="rw-status" :class="`is-${item.redemption_status}`">
                  {{ statusLabel(item.redemption_status) }}
                </span>
              </td>
              <td data-label="履约状态">
                <span
                  class="rw-status"
                  :class="`is-${item.status}`"
                  data-test="fulfillment-status"
                >
                  {{ statusLabel(item.status) }}
                </span>
              </td>
              <td data-label="创建时间">
                <time class="ark-data" :datetime="item.created_at ?? undefined">
                  {{ formatTime(item.created_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div v-if="availableActions(item).length > 0" class="rw-actions">
                  <button
                    v-for="action in availableActions(item)"
                    :key="action"
                    type="button"
                    class="rw-icon-button"
                    :data-test="`fulfillment-${action}-${item.id}`"
                    :aria-label="`${actionLabels[action].title}履约 #${item.id}`"
                    :title="`${actionLabels[action].title}履约 #${item.id}`"
                    :disabled="store.fulfillmentActionLoading"
                    @click="openAction(item, action)"
                  >
                    <Send v-if="action === 'issue'" :size="16" aria-hidden="true" />
                    <Ban v-else-if="action === 'cancel'" :size="16" aria-hidden="true" />
                    <BadgeCheck v-else :size="16" aria-hidden="true" />
                  </button>
                </div>
                <span v-else class="rw-processed">已处理</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div
      v-if="onlineCandidate"
      class="rw-dialog-backdrop"
      data-test="reward-online-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="rw-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rw-online-title"
      >
        <header>
          <h2 id="rw-online-title">
            {{ onlineCandidate.is_online ? '确认下架奖品' : '确认上架奖品' }}
          </h2>
          <button
            type="button"
            aria-label="关闭上架状态对话框"
            title="关闭"
            :disabled="store.rewardActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          「{{ onlineCandidate.name }}」{{
            onlineCandidate.is_online ? '下架后学员端立即不可兑换' : '上架后学员端按当前库存恢复可见'
          }}，历史兑换与履约记录保留。若该奖品已被其他管理员修改，本次操作会返回冲突。
        </p>
        <div class="rw-dialog__actions">
          <button
            type="button"
            data-test="confirm-online"
            :disabled="store.rewardActionLoading"
            @click="confirmOnlineToggle"
          >
            <Check :size="16" aria-hidden="true" />
            {{ store.rewardActionLoading ? '正在处理' : '确认' }}
          </button>
          <button
            type="button"
            data-test="dismiss-online"
            :disabled="store.rewardActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>

    <div
      v-if="actionCandidate"
      class="rw-dialog-backdrop"
      :data-test="`fulfillment-dialog-${actionCandidate.action}`"
      @click.self="closeDialogs"
    >
      <section
        class="rw-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rw-action-title"
      >
        <header>
          <h2 id="rw-action-title">
            确认{{ actionLabels[actionCandidate.action].button }}
          </h2>
          <button
            type="button"
            aria-label="关闭履约动作对话框"
            title="关闭"
            :disabled="store.fulfillmentActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          履约 #{{ actionCandidate.fulfillment.id }}（{{ actionCandidate.fulfillment.reward.name
          }}）{{
            actionCandidate.action === 'issue'
              ? '发放后状态变为已发放，并通知学员。'
              : actionCandidate.action === 'cancel'
                ? '取消后会在同一业务边界内回退积分、回滚库存并通知学员。'
                : '核销后状态变为已核销，不重复发放或回退积分。'
          }}
        </p>
        <div class="rw-dialog__actions">
          <button
            type="button"
            :data-test="`confirm-${actionCandidate.action}`"
            :disabled="store.fulfillmentActionLoading"
            @click="confirmAction"
          >
            <Check :size="16" aria-hidden="true" />
            {{ store.fulfillmentActionLoading ? actionLabels[actionCandidate.action].busy : actionLabels[actionCandidate.action].button }}
          </button>
          <button
            type="button"
            :data-test="`dismiss-${actionCandidate.action}`"
            :disabled="store.fulfillmentActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-rewards {
  min-width: 0;
  color: var(--ark-paper);
}

.rw-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rw-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 26px 24px;
}

.rw-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.rw-header__identity > div {
  min-width: 0;
}

.rw-header h1 {
  margin: 0;
  font-size: 2.2rem;
  line-height: 1;
}

.rw-header p {
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rw-header__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.rw-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.rw-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.9rem;
  line-height: 1;
}

.rw-message,
.rw-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rw-message {
  color: var(--ark-state);
}

.rw-message svg,
.rw-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.rw-message,
.rw-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rw-error button {
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

.rw-form,
.rw-registry,
.rw-queue {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.rw-form__heading,
.rw-registry__heading,
.rw-queue__heading {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.rw-form__heading > svg,
.rw-queue__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.rw-form__heading h2,
.rw-registry__heading h2,
.rw-queue__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.rw-form__heading span {
  min-width: 0;
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-registry__heading span,
.rw-queue__heading span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.rw-form__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  padding: 16px 18px;
}

.rw-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  align-content: start;
}

.rw-field > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-field input,
.rw-field select {
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

.rw-field input:hover {
  border-color: var(--ark-signal);
}

.rw-form__actions {
  display: flex;
  min-width: 0;
  align-items: flex-end;
  gap: 8px;
}

.rw-form__actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  flex: 1 1 auto;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-submit {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rw-form__error,
.rw-form__message {
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

.rw-form__error {
  color: var(--ark-signal);
}

.rw-form__message {
  color: var(--ark-state);
}

.rw-form__error svg,
.rw-form__message svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.rw-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.rw-state--empty {
  flex-direction: column;
}

.rw-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.rw-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.rw-table th,
.rw-table td {
  min-width: 0;
  padding: 13px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.rw-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
}

.rw-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rw-table time {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.rw-table th:nth-child(1) {
  width: 13%;
}

.rw-table th:nth-child(2) {
  width: 16%;
}

.rw-table th:nth-child(3),
.rw-table th:nth-child(4),
.rw-table th:nth-child(5),
.rw-table th:nth-child(6) {
  width: 8%;
}

.rw-table th:nth-child(7) {
  width: 9%;
}

.rw-table th:nth-child(8) {
  width: 6%;
}

.rw-table th:nth-child(9) {
  width: 12%;
}

.rw-table th:nth-child(10) {
  width: 12%;
}

.rw-table--queue th:nth-child(1) {
  width: 8%;
}

.rw-table--queue th:nth-child(2) {
  width: 17%;
}

.rw-table--queue th:nth-child(3) {
  width: 18%;
}

.rw-table--queue th:nth-child(4) {
  width: 8%;
}

.rw-table--queue th:nth-child(5),
.rw-table--queue th:nth-child(6) {
  width: 9%;
}

.rw-table--queue th:nth-child(7) {
  width: 13%;
}

.rw-table--queue th:nth-child(8) {
  width: 18%;
}

.rw-table tbody tr:last-child td {
  border-bottom: 0;
}

.rw-name {
  display: block;
  font-weight: 500;
}

.rw-sub {
  display: block;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.rw-status {
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

.rw-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.rw-status.is-online,
.rw-status.is-pending {
  color: var(--ark-signal);
}

.rw-status.is-offline,
.rw-status.is-canceled {
  color: var(--ark-muted);
}

.rw-status.is-issued {
  color: var(--ark-state);
}

.rw-status.is-verified {
  color: var(--ark-state);
}

.rw-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  min-width: 0;
}

.rw-actions button {
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
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-actions button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rw-actions button[aria-checked="true"] {
  color: var(--ark-state);
}

.rw-icon-button {
  width: 100%;
  min-height: 36px;
}

.rw-processed {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.rw-queue__filters {
  min-width: 0;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.rw-status-filter {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
}

.rw-status-filter button {
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

.rw-status-filter button:hover,
.rw-status-filter button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.rw-status-filter button.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.rw-search {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin-top: 12px;
}

.rw-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(5 6 7 / 0.72);
}

.rw-dialog {
  width: 100%;
  max-width: 560px;
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  box-shadow: 12px 14px 40px rgb(0 0 0 / 0.28);
}

.rw-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.rw-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.rw-dialog header button {
  display: inline-grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.rw-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.rw-dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.rw-dialog__actions button {
  display: inline-flex;
  min-width: 128px;
  min-height: 40px;
  flex: 0 1 auto;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.rw-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.admin-rewards :is(button, select, input):focus-visible {
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
  .rw-table-wrap {
    overflow-x: visible;
  }

  .rw-table,
  .rw-table tbody {
    display: block;
  }

  .rw-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .rw-table tbody {
    display: grid;
    gap: 1px;
    background: var(--ark-line);
  }

  .rw-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .rw-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .rw-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }

  .rw-table td:last-child {
    border-bottom: 0;
  }
}

@media (max-width: 1080px) {
  .rw-form__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rw-search {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .rw-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .rw-status-filter {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .rw-form__grid,
  .rw-search {
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-header__summary {
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-status-filter {
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .rw-dialog__actions button {
    min-width: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
