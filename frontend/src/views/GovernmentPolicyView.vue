<script setup lang="ts">
import {
  CheckCircle2,
  CircleOff,
  Eye,
  Filter,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Send,
  ShieldAlert,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type { GovernmentPolicy } from '@/api/types'
import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

type PolicyCategoryCode = GovernmentPolicy['category_code']
type PolicyStatus = GovernmentPolicy['status']

const policyCategories = [
  ['subsidy', '补贴'],
  ['ecommerce', '电商'],
  ['heritage', '非遗'],
  ['training', '培训'],
  ['certification', '认证'],
  ['general', '综合'],
  ['entrepreneurship', '创业支持']
] as const satisfies readonly (readonly [PolicyCategoryCode, string])[]

const policyStatuses = [
  ['active', '在架'],
  ['unpublished', '下架']
] as const satisfies readonly (readonly [PolicyStatus, string])[]

const store = useGovernmentConsoleStore()
const title = ref('')
const content = ref('')
const categoryCode = ref<PolicyCategoryCode>('subsidy')
const categoryFilter = ref<'all' | PolicyCategoryCode>('all')
const statusFilter = ref<'all' | PolicyStatus>('all')
const deleteCandidateId = ref<string | null>(null)
const actionMessage = ref('')
const initialLoading = ref(true)

const filteredPolicies = computed(() =>
  store.policies.filter(policy => {
    const matchesCategory =
      categoryFilter.value === 'all' ||
      policy.category_code === categoryFilter.value
    const matchesStatus =
      statusFilter.value === 'all' ||
      policy.status === statusFilter.value
    return matchesCategory && matchesStatus
  })
)

const activeCount = computed(
  () => store.policies.filter(policy => policy.status === 'active').length
)
const unpublishedCount = computed(
  () =>
    store.policies.filter(policy => policy.status === 'unpublished').length
)

function categoryLabel(category: PolicyCategoryCode): string {
  return (
    policyCategories.find(([code]) => code === category)?.[1] ?? category
  )
}

function statusLabel(status: PolicyStatus): string {
  return (
    policyStatuses.find(([code]) => code === status)?.[1] ?? status
  )
}

function formatPublishedAt(value: string): string {
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

async function loadPolicyList() {
  initialLoading.value = true
  try {
    await store.loadPolicies()
  } finally {
    initialLoading.value = false
  }
}

async function submitPolicy() {
  if (!title.value.trim() || !content.value.trim()) {
    return
  }

  actionMessage.value = ''
  const published = await store.publishPolicy({
    request_id: globalThis.crypto.randomUUID(),
    title: title.value.trim(),
    content: content.value.trim(),
    category_code: categoryCode.value
  })

  if (!published) {
    return
  }

  title.value = ''
  content.value = ''
  categoryCode.value = 'subsidy'
  actionMessage.value = '政策已发布并进入在架状态'
}

async function unpublishPolicy(policy: GovernmentPolicy) {
  actionMessage.value = ''
  const unpublished = await store.unpublishPolicy(
    policy.id,
    policy.version
  )
  if (unpublished) {
    actionMessage.value = '政策已下架，学员端将不再显示'
  }
}

async function relistPolicy(policy: GovernmentPolicy) {
  actionMessage.value = ''
  const relisted = await store.relistPolicy(policy.id, policy.version)
  if (relisted) {
    actionMessage.value = '政策已重新上架，不会重复发送订阅通知'
  }
}

function requestDelete(policy: GovernmentPolicy) {
  actionMessage.value = ''
  deleteCandidateId.value = policy.id
}

function cancelDelete() {
  deleteCandidateId.value = null
}

async function confirmDelete(policy: GovernmentPolicy) {
  actionMessage.value = ''
  const deleted = await store.deletePolicy(policy.id, policy.version)
  deleteCandidateId.value = null
  if (deleted) {
    actionMessage.value = '政策已彻底删除，浏览计数同时移除'
  }
}

onMounted(() => {
  void loadPolicyList()
})
</script>

<template>
  <div class="government-policy-page" data-test="government-policy-page">
    <GovernmentConsoleNav />

    <main
      class="government-policy"
      data-ark-theme="ark"
      data-ark-depth="maximal"
    >
      <header class="policy-hero">
        <div class="policy-hero__identity">
          <ScrollText :size="25" aria-hidden="true" />
          <div>
            <span class="ark-data">POLICY REGISTRY</span>
            <h1>政策管理</h1>
            <p>
              发布七类政策并维护在架、下架和删除状态。
              已发布内容本期仅维护生命周期状态。
            </p>
          </div>
        </div>

        <dl class="policy-hero__summary" aria-label="政策状态概览">
          <div>
            <dt>在架</dt>
            <dd class="ark-data">{{ activeCount }}</dd>
          </div>
          <div>
            <dt>下架</dt>
            <dd class="ark-data">{{ unpublishedCount }}</dd>
          </div>
        </dl>
      </header>

      <section class="policy-compose" aria-labelledby="policy-compose-title">
        <header class="section-heading">
          <div>
            <span class="ark-data">PUBLISH POLICY</span>
            <h2 id="policy-compose-title">发布政策</h2>
          </div>
          <span class="ark-data">七类</span>
        </header>

        <form
          class="policy-form"
          data-test="policy-form"
          @submit.prevent="submitPolicy"
        >
          <div class="policy-compose__grid">
            <label class="policy-field">
              <span>政策标题</span>
              <input
                v-model="title"
                data-test="policy-title"
                name="title"
                type="text"
                maxlength="120"
                autocomplete="off"
                required
              />
            </label>

            <label class="policy-field">
              <span>政策分类</span>
              <select
                v-model="categoryCode"
                data-test="policy-category"
                name="category_code"
                required
              >
                <option
                  v-for="[code, label] in policyCategories"
                  :key="code"
                  :value="code"
                >
                  {{ label }}
                </option>
              </select>
            </label>

            <label class="policy-field policy-field--wide">
              <span>政策正文</span>
              <textarea
                v-model="content"
                data-test="policy-content"
                name="content"
                rows="6"
                required
              />
            </label>
          </div>

          <div class="policy-compose__actions">
            <p>
              发布即上架，并立即向当前订阅该分类的学员发送通知。
            </p>
            <button
              class="policy-submit"
              type="submit"
              :disabled="
                store.loading ||
                !title.trim() ||
                !content.trim()
              "
            >
              <Send :size="17" aria-hidden="true" />
              {{ store.loading ? '发布中' : '发布政策' }}
            </button>
          </div>
        </form>
      </section>

      <div
        v-if="actionMessage"
        class="policy-message"
        data-test="policy-message"
        role="status"
      >
        <CheckCircle2 :size="18" aria-hidden="true" />
        <span>{{ actionMessage }}</span>
      </div>

      <div
        v-if="store.error"
        class="policy-error"
        data-test="policy-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.error }}</span>
        <button type="button" @click="loadPolicyList">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <section class="policy-registry" aria-labelledby="policy-registry-title">
        <header class="section-heading policy-registry__heading">
          <div>
            <span class="ark-data">POLICY REGISTRY</span>
            <h2 id="policy-registry-title">政策目录</h2>
          </div>
          <span class="ark-data">{{ filteredPolicies.length }} 条</span>
        </header>

        <div class="policy-registry__filters">
          <label class="policy-field">
            <span>
              <Filter :size="15" aria-hidden="true" />
              分类筛选
            </span>
            <select
              v-model="categoryFilter"
              data-test="policy-category-filter"
            >
              <option value="all">全部分类</option>
              <option
                v-for="[code, label] in policyCategories"
                :key="code"
                :value="code"
              >
                {{ label }}
              </option>
            </select>
          </label>

          <label class="policy-field">
            <span>状态筛选</span>
            <select
              v-model="statusFilter"
              data-test="policy-status-filter"
            >
              <option value="all">全部状态</option>
              <option
                v-for="[code, label] in policyStatuses"
                :key="code"
                :value="code"
              >
                {{ label }}
              </option>
            </select>
          </label>
        </div>

        <div
          v-if="
            (initialLoading || store.loading) &&
            store.policies.length === 0
          "
          class="policy-status"
          data-test="policy-loading"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          正在加载政策
        </div>

        <p
          v-else-if="filteredPolicies.length === 0"
          class="policy-empty"
          data-test="policy-empty"
        >
          暂无符合条件的政策
        </p>

        <div v-else class="policy-table-wrap">
          <table class="policy-table">
            <colgroup>
              <col class="policy-table__col-title" />
              <col class="policy-table__col-category" />
              <col class="policy-table__col-status" />
              <col class="policy-table__col-views" />
              <col class="policy-table__col-published" />
              <col class="policy-table__col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">政策标题</th>
                <th scope="col">分类</th>
                <th scope="col">状态</th>
                <th scope="col">浏览量</th>
                <th scope="col">发布时间</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="policy in filteredPolicies"
                :key="policy.id"
                data-test="policy-row"
                :data-policy-id="policy.id"
              >
                <td data-label="政策标题">
                  <div class="policy-table__title">
                    <strong>{{ policy.title }}</strong>
                    <span class="ark-data">版本 {{ policy.version }}</span>
                  </div>
                </td>
                <td data-label="分类">
                  {{ categoryLabel(policy.category_code) }}
                </td>
                <td data-label="状态">
                  <span
                    class="policy-state"
                    :class="`is-${policy.status}`"
                    data-test="policy-status"
                  >
                    {{ statusLabel(policy.status) }}
                  </span>
                </td>
                <td data-label="浏览量">
                  <span class="policy-views ark-data">
                    <Eye :size="15" aria-hidden="true" />
                    {{ policy.view_count }}
                  </span>
                </td>
                <td data-label="发布时间">
                  <time
                    class="ark-data policy-published-at"
                    :datetime="policy.published_at"
                  >
                    {{ formatPublishedAt(policy.published_at) }}
                  </time>
                </td>
                <td data-label="操作">
                  <div class="policy-actions">
                    <button
                      v-if="policy.status === 'active'"
                      type="button"
                      data-test="unpublish-policy"
                      :aria-label="`下架政策：${policy.title}`"
                      :title="`下架政策：${policy.title}`"
                      :disabled="store.loading"
                      @click="unpublishPolicy(policy)"
                    >
                      <CircleOff :size="16" aria-hidden="true" />
                      <span>下架</span>
                    </button>
                    <button
                      v-else
                      type="button"
                      data-test="relist-policy"
                      :aria-label="`重新上架政策：${policy.title}`"
                      :title="`重新上架政策：${policy.title}`"
                      :disabled="store.loading"
                      @click="relistPolicy(policy)"
                    >
                      <RotateCcw :size="16" aria-hidden="true" />
                      <span>重新上架</span>
                    </button>
                    <button
                      class="policy-delete-trigger"
                      type="button"
                      data-test="delete-policy"
                      :aria-label="`删除政策：${policy.title}`"
                      :title="`删除政策：${policy.title}`"
                      :disabled="store.loading"
                      @click="requestDelete(policy)"
                    >
                      <Trash2 :size="16" aria-hidden="true" />
                      <span>删除</span>
                    </button>
                  </div>

                  <div
                    v-if="deleteCandidateId === policy.id"
                    class="policy-delete-confirmation"
                    data-test="policy-delete-confirmation"
                  >
                    <p>
                      确认彻底删除「{{ policy.title }}」？内容和浏览计数将移除，
                      已发送的历史通知不会撤回。
                    </p>
                    <div>
                      <button
                        type="button"
                        data-test="confirm-delete-policy"
                        :disabled="store.loading"
                        @click="confirmDelete(policy)"
                      >
                        <Trash2 :size="15" aria-hidden="true" />
                        确认删除
                      </button>
                      <button
                        type="button"
                        data-test="cancel-delete-policy"
                        :disabled="store.loading"
                        @click="cancelDelete"
                      >
                        <X :size="15" aria-hidden="true" />
                        取消
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.government-policy-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.government-policy {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color: var(--ark-paper);
}

.policy-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, 0.62fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.policy-hero__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.policy-hero__identity > svg {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--ark-signal);
}

.policy-hero__identity > div {
  min-width: 0;
}

.policy-hero__identity span,
.section-heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.policy-hero__identity h1 {
  margin: 4px 0 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.policy-hero__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-hero__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.policy-hero__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 20px 24px;
  background: var(--ark-surface-1);
}

.policy-hero__summary dt {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.policy-hero__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 2.2rem;
  line-height: 1;
}

.policy-compose,
.policy-registry {
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
  text-wrap: balance;
}

.policy-form {
  min-width: 0;
  padding: 18px;
}

.policy-compose__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(190px, 0.75fr);
  gap: 14px;
  min-width: 0;
}

.policy-field {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.policy-field > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  word-break: keep-all;
}

.policy-field input,
.policy-field select,
.policy-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.policy-field textarea {
  min-height: 138px;
  resize: vertical;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.policy-field input::placeholder,
.policy-field textarea::placeholder {
  color: var(--ark-muted);
}

.policy-field input:hover,
.policy-field select:hover,
.policy-field textarea:hover {
  border-color: var(--ark-signal);
}

.policy-field--wide {
  grid-column: 1 / -1;
}

.policy-compose__actions {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 16px;
}

.policy-compose__actions p {
  max-width: 65ch;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-submit,
.policy-error button,
.policy-actions button,
.policy-delete-confirmation button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.policy-submit {
  flex: 0 0 auto;
  min-height: 44px;
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.policy-submit:hover:not(:disabled),
.policy-error button:hover:not(:disabled),
.policy-actions button:hover:not(:disabled),
.policy-delete-confirmation button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.policy-message,
.policy-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.policy-message {
  color: var(--ark-state);
}

.policy-message svg,
.policy-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.policy-message span,
.policy-error > span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-error {
  color: var(--ark-paper);
}

.policy-error button {
  flex: 0 0 auto;
  margin-left: auto;
}

.policy-registry__filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  gap: 14px;
  min-width: 0;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.policy-status,
.policy-empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.policy-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.policy-table__col-title {
  width: 25%;
}

.policy-table__col-category {
  width: 11%;
}

.policy-table__col-status {
  width: 10%;
}

.policy-table__col-views {
  width: 10%;
}

.policy-table__col-published {
  width: 18%;
}

.policy-table__col-actions {
  width: 26%;
}

.policy-table th,
.policy-table td {
  min-width: 0;
  padding: 14px 12px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.policy-table th {
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-weight: 500;
  line-break: strict;
  white-space: nowrap;
  word-break: keep-all;
}

.policy-table td {
  color: var(--ark-paper);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.policy-table tbody tr:last-child td {
  border-bottom: 0;
}

.policy-table__title {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.policy-table__title strong {
  min-width: 0;
  line-height: 1.35;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-table__title span,
.policy-published-at {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.policy-state,
.policy-views {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.policy-state::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: var(--ark-muted);
  content: "";
}

.policy-state.is-active {
  color: var(--ark-state);
}

.policy-state.is-active::before {
  background: var(--ark-state);
}

.policy-state.is-unpublished {
  color: var(--ark-signal);
}

.policy-state.is-unpublished::before {
  background: var(--ark-signal);
}

.policy-views svg {
  color: var(--ark-muted);
}

.policy-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.policy-actions button {
  flex: 1 1 88px;
}

.policy-delete-trigger {
  border-color: var(--ark-line-strong);
}

.policy-delete-confirmation {
  margin-top: 10px;
  padding: 11px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.policy-delete-confirmation p {
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.policy-delete-confirmation > div {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 9px;
}

.policy-delete-confirmation button {
  flex: 1 1 100px;
}

.policy-delete-confirmation button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.government-policy :is(button, a, input, select, textarea):focus-visible {
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

@media (max-width: 760px), (orientation: portrait) {
  .government-policy {
    padding: 28px 14px 48px;
  }

  .policy-hero {
    grid-template-columns: minmax(0, 1fr);
  }

  .policy-hero__identity {
    padding: 20px 16px;
  }

  .policy-hero__identity h1 {
    font-size: 2.15rem;
  }

  .policy-hero__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .policy-hero__summary div {
    padding: 16px;
  }

  .policy-compose__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .policy-compose__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .policy-submit {
    width: 100%;
  }

  .policy-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .policy-error button {
    width: 100%;
    margin-left: 0;
  }

  .policy-table-wrap {
    overflow-x: visible;
  }

  .policy-table {
    display: block;
    table-layout: auto;
  }

  .policy-table colgroup,
  .policy-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .policy-table tbody {
    display: grid;
    min-width: 0;
    gap: 1px;
    background: var(--ark-line);
  }

  .policy-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .policy-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .policy-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
    line-break: strict;
    word-break: keep-all;
  }

  .policy-table td:last-child {
    border-bottom: 0;
  }

  .policy-table__title {
    justify-items: end;
    text-align: right;
  }

  .policy-actions {
    justify-content: flex-end;
  }

  .policy-delete-confirmation {
    grid-column: 1 / -1;
    text-align: left;
  }
}

@media (max-width: 420px) {
  .policy-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .policy-table__title {
    justify-items: start;
    text-align: left;
  }

  .policy-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    width: 100%;
  }

  .policy-actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
