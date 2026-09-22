
<script setup lang="ts">
import {
  Check,
  Inbox,
  KeyRound,
  Power,
  PowerOff,
  RefreshCw,
  ScanEye,
  Search,
  ShieldAlert,
  UserPlus,
  Users,
  X
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  AdminAccount,
  AdminAccountRoleFilter,
  AdminManagedRole
} from '@/api/types'
import { useAdminConsoleStore } from '@/stores/adminConsole'

const roleOptions: ReadonlyArray<{
  value: AdminAccountRoleFilter
  label: string
}> = [
  { value: 'all', label: '全部' },
  { value: 'enterprise', label: '企业账户' },
  { value: 'government', label: '政府账户' },
  { value: 'admin', label: '普通管理员' },
  { value: 'super_admin', label: '超级管理员' }
]

const createRoleOptions: ReadonlyArray<{
  value: AdminManagedRole
  label: string
}> = roleOptions.filter(
    (option): option is { value: AdminManagedRole; label: string } =>
      option.value !== 'all'
  )

const roleLabels: Record<AdminManagedRole, string> = {
  enterprise: '企业账户',
  government: '政府账户',
  admin: '普通管理员',
  super_admin: '超级管理员'
}

const store = useAdminConsoleStore()
const roleFilter = ref<AdminAccountRoleFilter>('all')
const keyword = ref('')
const createOpen = ref(false)
const createMessage = ref('')
const actionMessage = ref('')
const selectedId = ref<number | null>(null)
const toggleCandidate = ref<AdminAccount | null>(null)
const resetCandidate = ref<AdminAccount | null>(null)
const form = ref<{
  role: AdminManagedRole
  username: string
  name: string
  password: string
}>({ role: 'enterprise', username: '', name: '', password: '' })

let keywordTimer: ReturnType<typeof setTimeout> | undefined

const selectedAccount = computed(
  () => store.accounts.find(account => account.id === selectedId.value) ?? null
)

const disabledCount = computed(
  () => store.accounts.filter(account => !account.is_enabled).length
)

const canSubmit = computed(
  () =>
    form.value.username.trim().length > 0 && form.value.password.length >= 8
)

function roleLabel(role: AdminManagedRole): string {
  return roleLabels[role] ?? role
}

function formatTime(value: string): string {
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

function reloadAccounts(): void {
  void store.loadAccounts(
    roleFilter.value === 'all' ? null : roleFilter.value,
    keyword.value.trim()
  )
}

watch(roleFilter, reloadAccounts)

watch(keyword, () => {
  if (keywordTimer) {
    clearTimeout(keywordTimer)
  }
  keywordTimer = setTimeout(reloadAccounts, 240)
})

function toggleCreateForm(): void {
  createOpen.value = !createOpen.value
  createMessage.value = ''
}

function openDetail(account: AdminAccount): void {
  actionMessage.value = ''
  selectedId.value = account.id
}

function openToggle(account: AdminAccount): void {
  actionMessage.value = ''
  toggleCandidate.value = account
}

function openReset(account: AdminAccount): void {
  actionMessage.value = ''
  resetCandidate.value = account
}

function closeDialogs(): void {
  toggleCandidate.value = null
  resetCandidate.value = null
}

async function confirmToggle(): Promise<void> {
  const account = toggleCandidate.value
  if (account === null) return
  const enabled = !account.is_enabled
  const done = await store.setAccountEnabled(account.id, enabled)
  if (done) {
    actionMessage.value = `已${enabled ? '启用' : '禁用'}账户「${account.username}」`
    closeDialogs()
  }
}

async function confirmReset(): Promise<void> {
  const account = resetCandidate.value
  if (account === null) return
  const done = await store.resetPassword(account.id)
  if (done) {
    actionMessage.value = `已重置「${account.username}」的登录密码`
    closeDialogs()
  }
}

async function submitAccount(): Promise<void> {
  if (!canSubmit.value) return
  const payload = {
    role: form.value.role,
    username: form.value.username.trim(),
    name: form.value.name.trim(),
    password: form.value.password
  }
  const done = await store.createAccount(payload)
  if (done) {
    createMessage.value = `已创建账户「${payload.username}」，初始密码请线下送达`
    form.value = {
      role: form.value.role,
      username: '',
      name: '',
      password: ''
    }
  }
}

onMounted(reloadAccounts)

onBeforeUnmount(() => {
  if (keywordTimer) {
    clearTimeout(keywordTimer)
  }
})
</script>

<template>
  <section class="admin-accounts" data-test="admin-accounts">
    <header class="accounts-header">
      <div class="accounts-header__identity">
        <Users :size="26" aria-hidden="true" />
        <div>
          <h1>账户管理</h1>
          <p>企业、政府与管理员账户的统一维护入口。</p>
        </div>
      </div>
      <dl class="accounts-header__summary">
        <div>
          <dt>当前列表</dt>
          <dd class="ark-data">{{ store.accounts.length }}</dd>
        </div>
        <div>
          <dt>已禁用</dt>
          <dd class="ark-data">{{ disabledCount }}</dd>
        </div>
      </dl>
    </header>

    <div class="accounts-filters">
      <div
        class="accounts-roles"
        role="group"
        aria-label="按角色筛选账户"
        data-test="account-role-filter"
      >
        <button
          v-for="option in roleOptions"
          :key="option.value"
          type="button"
          :data-test="`account-filter-${option.value}`"
          :class="{ 'is-active': roleFilter === option.value }"
          :aria-pressed="roleFilter === option.value"
          @click="roleFilter = option.value"
        >
          <span>{{ option.label }}</span>
        </button>
      </div>

      <label class="accounts-search">
        <Search :size="17" aria-hidden="true" />
        <input
          v-model="keyword"
          type="search"
          data-test="account-search"
          placeholder="搜索用户名或姓名"
          aria-label="按用户名或姓名搜索账户"
        />
      </label>
    </div>

    <p
      v-if="actionMessage"
      class="accounts-message"
      data-test="account-action-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ actionMessage }}
    </p>

    <section class="accounts-create" aria-labelledby="accounts-create-title">
      <header class="accounts-create__heading">
        <UserPlus :size="20" aria-hidden="true" />
        <h2 id="accounts-create-title">新建账户</h2>
        <span>初始密码仅保存哈希。</span>
      </header>
      <button
        v-if="!createOpen"
        type="button"
        class="accounts-create__trigger"
        data-test="account-create"
        :aria-expanded="createOpen"
        @click="toggleCreateForm"
      >
        <UserPlus :size="16" aria-hidden="true" />
        新建账户
      </button>
      <form
        v-else
        class="accounts-create__form"
        data-test="account-create-form"
        @submit.prevent="submitAccount"
      >
        <label class="accounts-field">
          <span>角色</span>
          <select v-model="form.role" data-test="account-role">
            <option
              v-for="option in createRoleOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="accounts-field">
          <span>用户名</span>
          <input
            v-model.trim="form.username"
            type="text"
            data-test="account-username"
            maxlength="32"
            autocomplete="off"
          />
        </label>
        <label class="accounts-field">
          <span>姓名</span>
          <input
            v-model.trim="form.name"
            type="text"
            data-test="account-name"
            maxlength="30"
            autocomplete="off"
          />
        </label>
        <label class="accounts-field">
          <span>初始密码</span>
          <input
            v-model="form.password"
            type="password"
            data-test="account-password"
            maxlength="72"
            autocomplete="new-password"
          />
        </label>
        <button
          type="submit"
          class="accounts-submit"
          data-test="account-submit"
          :disabled="!canSubmit || store.accountActionLoading"
        >
          <UserPlus :size="16" aria-hidden="true" />
          {{ store.accountActionLoading ? '正在创建' : '创建账户' }}
        </button>
      </form>
      <p
        v-if="createMessage"
        class="accounts-message"
        data-test="account-create-message"
        role="status"
      >
        <Check :size="17" aria-hidden="true" />
        {{ createMessage }}
      </p>
    </section>

    <section class="accounts-registry" aria-labelledby="accounts-registry-title">
      <header class="accounts-registry__heading">
        <h2 id="accounts-registry-title">账户列表</h2>
        <span class="ark-data">{{ store.accounts.length }} 条</span>
      </header>

      <div
        v-if="store.accountsLoading && store.accounts.length === 0"
        class="accounts-state"
        data-test="account-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载账户列表
      </div>

      <div
        v-else-if="store.accountsError"
        class="accounts-error"
        data-test="account-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.accountsError }}</span>
        <button
          type="button"
          data-test="account-retry"
          :disabled="store.accountsLoading"
          @click="reloadAccounts"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <div
        v-else-if="store.accounts.length === 0"
        class="accounts-state accounts-state--empty"
        data-test="account-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>暂无符合条件的账户</span>
      </div>

      <div v-else class="accounts-table-wrap">
        <table class="accounts-table" data-test="account-table">
          <thead>
            <tr>
              <th scope="col">用户 ID</th>
              <th scope="col">用户名</th>
              <th scope="col">姓名</th>
              <th scope="col">角色</th>
              <th scope="col">状态</th>
              <th scope="col">创建时间</th>
              <th scope="col">更新时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="account in store.accounts"
              :key="account.id"
              data-test="account-row"
              :data-account-id="account.id"
            >
              <td data-label="用户 ID">
                <span class="ark-data">#{{ account.id }}</span>
              </td>
              <td data-label="用户名">
                <span class="accounts-username">{{ account.username }}</span>
              </td>
              <td data-label="姓名">{{ account.name }}</td>
              <td data-label="角色">{{ roleLabel(account.role) }}</td>
              <td data-label="状态">
                <span
                  class="accounts-status"
                  :class="account.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="account-status"
                >
                  {{ account.is_enabled ? '已启用' : '已禁用' }}
                </span>
              </td>
              <td data-label="创建时间">
                <time class="ark-data" :datetime="account.created_at">
                  {{ formatTime(account.created_at) }}
                </time>
              </td>
              <td data-label="更新时间">
                <time class="ark-data" :datetime="account.updated_at">
                  {{ formatTime(account.updated_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div class="accounts-actions">
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="account.is_enabled"
                    :aria-label="`${account.is_enabled ? '禁用' : '启用'}账户：${account.username}`"
                    :title="`${account.is_enabled ? '禁用' : '启用'}账户：${account.username}`"
                    data-test="account-toggle"
                    :disabled="store.accountActionLoading"
                    @click="openToggle(account)"
                  >
                    <Power v-if="account.is_enabled" :size="16" aria-hidden="true" />
                    <PowerOff v-else :size="16" aria-hidden="true" />
                    {{ account.is_enabled ? '禁用' : '启用' }}
                  </button>
                  <button
                    type="button"
                    :aria-label="`重置密码：${account.username}`"
                    :title="`重置密码：${account.username}`"
                    data-test="account-reset"
                    :disabled="store.accountActionLoading"
                    @click="openReset(account)"
                  >
                    <KeyRound :size="16" aria-hidden="true" />
                    重置密码
                  </button>
                  <button
                    type="button"
                    :aria-label="`查看详情：${account.username}`"
                    :title="`查看详情：${account.username}`"
                    data-test="account-detail"
                    @click="openDetail(account)"
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
      v-if="selectedAccount"
      class="accounts-detail"
      aria-labelledby="accounts-detail-title"
      data-test="account-detail-panel"
    >
      <header class="accounts-detail__heading">
        <ScanEye :size="20" aria-hidden="true" />
        <h2 id="accounts-detail-title">账户详情</h2>
        <span class="ark-data">#{{ selectedAccount.id }}</span>
      </header>
      <dl class="accounts-detail__grid">
        <div>
          <dt>用户名</dt>
          <dd>{{ selectedAccount.username }}</dd>
        </div>
        <div>
          <dt>姓名</dt>
          <dd>{{ selectedAccount.name }}</dd>
        </div>
        <div>
          <dt>角色</dt>
          <dd>{{ roleLabel(selectedAccount.role) }}</dd>
        </div>
        <div>
          <dt>启用状态</dt>
          <dd>{{ selectedAccount.is_enabled ? '已启用' : '已禁用' }}</dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd class="ark-data">{{ formatTime(selectedAccount.created_at) }}</dd>
        </div>
        <div>
          <dt>更新时间</dt>
          <dd class="ark-data">{{ formatTime(selectedAccount.updated_at) }}</dd>
        </div>
      </dl>
    </section>

    <div
      v-if="toggleCandidate"
      class="accounts-dialog-backdrop"
      data-test="account-toggle-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="accounts-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="accounts-toggle-title"
      >
        <header>
          <h2 id="accounts-toggle-title">
            {{ toggleCandidate.is_enabled ? '确认禁用账户' : '确认启用账户' }}
          </h2>
          <button
            type="button"
            aria-label="关闭账户状态对话框"
            title="关闭"
            :disabled="store.accountActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          「{{ toggleCandidate.username }}」
          {{ toggleCandidate.is_enabled ? '禁用后' : '启用后' }}该账户的下一次登录与受保护操作将立即
          {{ toggleCandidate.is_enabled ? '被拒绝' : '恢复' }}，业务数据保持不变。
        </p>
        <div class="accounts-dialog__actions">
          <button
            type="button"
            data-test="account-toggle-confirm"
            :disabled="store.accountActionLoading"
            @click="confirmToggle"
          >
            <Check :size="16" aria-hidden="true" />
            {{ store.accountActionLoading ? '正在处理' : '确认' }}
          </button>
          <button
            type="button"
            :disabled="store.accountActionLoading"
            data-test="account-toggle-cancel"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>

    <div
      v-if="resetCandidate"
      class="accounts-dialog-backdrop"
      data-test="account-reset-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="accounts-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="accounts-reset-title"
      >
        <header>
          <h2 id="accounts-reset-title">确认重置密码</h2>
          <button
            type="button"
            aria-label="关闭重置密码对话框"
            title="关闭"
            :disabled="store.accountActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p>
          为「{{ resetCandidate.username }}」生成新的初始密码，仅保存密码哈希。新密码通过
          02 站内通知或线下方式送达，本页面不展示密码内容。
        </p>
        <div class="accounts-dialog__actions">
          <button
            type="button"
            data-test="account-reset-confirm"
            :disabled="store.accountActionLoading"
            @click="confirmReset"
          >
            <KeyRound :size="16" aria-hidden="true" />
            {{ store.accountActionLoading ? '正在处理' : '确认重置' }}
          </button>
          <button
            type="button"
            :disabled="store.accountActionLoading"
            data-test="account-reset-cancel"
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
.admin-accounts {
  min-width: 0;
  color: var(--ark-paper);
}

.accounts-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.accounts-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 26px 24px;
}

.accounts-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.accounts-header__identity > div {
  min-width: 0;
}

.accounts-header h1 {
  margin: 0;
  font-size: 2.2rem;
  line-height: 1;
}

.accounts-header p {
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.accounts-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.accounts-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 18px 20px;
  background: var(--ark-surface-1);
}

.accounts-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.accounts-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.9rem;
  line-height: 1;
}

.accounts-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 14px;
  min-width: 0;
  margin-top: 18px;
}

.accounts-roles {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
}

.accounts-roles button {
  display: flex;
  min-width: 0;
  min-height: 56px;
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

.accounts-roles button:hover,
.accounts-roles button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.accounts-roles button.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.accounts-search {
  display: flex;
  min-width: 0;
  min-height: 56px;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.accounts-search > svg {
  flex: 0 0 auto;
  color: var(--ark-muted);
}

.accounts-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.accounts-message,
.accounts-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.accounts-message {
  color: var(--ark-state);
}

.accounts-message svg,
.accounts-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.accounts-message,
.accounts-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.accounts-error button {
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

.accounts-create {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.accounts-create__heading {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.accounts-create__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.accounts-create__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.accounts-create__heading span {
  min-width: 0;
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.accounts-create__trigger {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  gap: 8px;
  margin: 16px 18px;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
  font-size: 0.84rem;
}

.accounts-create__form {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  padding: 16px 18px;
}

.accounts-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  align-content: start;
}

.accounts-field > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.accounts-field select,
.accounts-field input {
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

.accounts-field select:hover,
.accounts-field input:hover {
  border-color: var(--ark-signal);
}

.accounts-submit {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  align-self: end;
  padding: 0 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
  font-size: 0.84rem;
}

.accounts-registry {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.accounts-registry__heading {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.accounts-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.accounts-registry__heading span {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.accounts-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.accounts-state--empty {
  flex-direction: column;
}

.accounts-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.accounts-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.accounts-table th,
.accounts-table td {
  min-width: 0;
  padding: 13px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.accounts-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
}

.accounts-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.accounts-table th:nth-child(1) {
  width: 7%;
}

.accounts-table th:nth-child(2) {
  width: 14%;
}

.accounts-table th:nth-child(3) {
  width: 12%;
}

.accounts-table th:nth-child(4) {
  width: 12%;
}

.accounts-table th:nth-child(5) {
  width: 10%;
}

.accounts-table th:nth-child(6) {
  width: 13%;
}

.accounts-table th:nth-child(7) {
  width: 13%;
}

.accounts-table th:nth-child(8) {
  width: 19%;
}

.accounts-table tbody tr:last-child td {
  border-bottom: 0;
}

.accounts-username {
  display: block;
  font-weight: 500;
}

.accounts-table time {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.accounts-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  font-size: 0.72rem;
  white-space: nowrap;
}

.accounts-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.accounts-status.is-enabled {
  color: var(--ark-state);
}

.accounts-status.is-disabled {
  color: var(--ark-muted);
}

.accounts-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  min-width: 0;
}

.accounts-actions button {
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

.accounts-actions button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.accounts-actions button[aria-checked="true"] {
  color: var(--ark-state);
}

.accounts-detail {
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.accounts-detail__heading {
  display: flex;
  min-width: 0;
  min-height: 58px;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.accounts-detail__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.accounts-detail__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.accounts-detail__heading span {
  margin-left: auto;
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.accounts-detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  background: var(--ark-line);
}

.accounts-detail__grid div {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 14px 18px;
  background: var(--ark-surface-1);
}

.accounts-detail__grid dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.accounts-detail__grid dd {
  margin: 0;
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.accounts-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(5 6 7 / 0.72);
}

.accounts-dialog {
  width: 100%;
  max-width: 560px;
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  box-shadow: 12px 14px 40px rgb(0 0 0 / 0.28);
}

.accounts-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.accounts-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.accounts-dialog header button {
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

.accounts-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.accounts-dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.accounts-dialog__actions button {
  display: inline-flex;
  min-width: 0;
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
}

.accounts-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.admin-accounts :is(button, select, input):focus-visible {
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
  .accounts-table-wrap {
    overflow-x: visible;
  }

  .accounts-table,
  .accounts-table tbody {
    display: block;
  }

  .accounts-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .accounts-table tbody {
    display: grid;
    gap: 1px;
    background: var(--ark-line);
  }

  .accounts-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .accounts-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .accounts-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
  }

  .accounts-table td:last-child {
    border-bottom: 0;
  }
}

@media (max-width: 1080px) {
  .accounts-create__form {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .accounts-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .accounts-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .accounts-filters {
    grid-template-columns: minmax(0, 1fr);
  }

  .accounts-roles {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .accounts-create__form {
    grid-template-columns: minmax(0, 1fr);
  }

  .accounts-roles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .accounts-detail__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .accounts-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .accounts-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
