<script setup lang="ts">
import {
  AlertCircle,
  ClipboardList,
  RefreshCw,
  SlidersHorizontal
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import type {
  ApplicationStatus,
  EnterpriseApplicationFilters
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EnterpriseApplicationStatusBadge from '@/components/EnterpriseApplicationStatusBadge.vue'
import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

type ApplicationSort = NonNullable<EnterpriseApplicationFilters['sort']>

interface ApplicationFilterForm {
  job_id: string
  status: ApplicationStatus | ''
  submitted_from: string
  submitted_to: string
  sort: ApplicationSort
}

const store = useEnterpriseConsoleStore()
const auth = useAuthStore()
const router = useRouter()
const pageLoading = ref(false)
const pageError = ref('')
const filters = reactive<ApplicationFilterForm>({
  job_id: store.applicationFilters.job_id ?? '',
  status: store.applicationFilters.status ?? '',
  submitted_from: store.applicationFilters.submitted_from ?? '',
  submitted_to: store.applicationFilters.submitted_to ?? '',
  sort: store.applicationFilters.sort ?? 'submitted_desc'
})

const submittedAtFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23'
})

const displayError = computed(() => pageError.value || store.error)
const isBusy = computed(() => pageLoading.value || store.loading || store.saving)
const jobOptions = computed(() => {
  const options = new Map<string, string>()

  for (const job of store.jobs) {
    if (!job.deleted_at) {
      options.set(job.job_id, job.title)
    }
  }

  for (const application of store.applications) {
    options.set(application.job_id, application.job_title)
  }

  return Array.from(options, ([jobId, title]) => ({
    jobId,
    title
  }))
})

function applicationPath(applicationId: string): string {
  return `/enterprise/applications/${encodeURIComponent(applicationId)}`
}

function formatSubmittedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  const values = Object.fromEntries(
    submittedAtFormatter
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )

  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`
}

function normalizedFilters(): EnterpriseApplicationFilters {
  return {
    job_id: filters.job_id.trim() || undefined,
    status: filters.status || undefined,
    submitted_from: filters.submitted_from.trim() || undefined,
    submitted_to: filters.submitted_to.trim() || undefined,
    sort: filters.sort
  }
}

async function loadApplications(
  nextFilters: EnterpriseApplicationFilters = store.applicationFilters
) {
  pageLoading.value = true
  pageError.value = ''

  const loaded = await store.loadApplications(nextFilters)
  if (!loaded) {
    pageError.value = store.error
  }

  pageLoading.value = false
}

async function submitFilters() {
  await loadApplications(normalizedFilters())
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadApplications(store.applicationFilters)
})
</script>

<template>
  <div class="enterprise-applications-page">
    <AppHeader
      source="live"
      :loading="isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EnterpriseConsoleNav />

    <main class="enterprise-applications-main">
      <header class="applications-heading">
        <span class="ark-data">09 / APPLICATIONS</span>
        <h1>申请处理</h1>
        <p>
          按职位、状态和投递日期筛选本企业收到的申请，查看快照并记录处理状态。
        </p>
      </header>

      <form
        class="application-filter-form"
        data-test="application-filter-form"
        @submit.prevent="submitFilters"
      >
        <label class="application-filter-field">
          <span>职位</span>
          <select
            v-model="filters.job_id"
            data-test="application-job-filter"
          >
            <option value="">全部职位</option>
            <option
              v-for="option in jobOptions"
              :key="option.jobId"
              :value="option.jobId"
            >
              {{ option.title }}
            </option>
          </select>
        </label>

        <label class="application-filter-field">
          <span>状态</span>
          <select
            v-model="filters.status"
            data-test="application-status-filter"
          >
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="viewed">已查看</option>
            <option value="intent">意向沟通</option>
            <option value="unsuitable">不合适</option>
          </select>
        </label>

        <label class="application-filter-field">
          <span>投递起始日</span>
          <input
            v-model="filters.submitted_from"
            data-test="application-submitted-from"
            type="date"
          >
        </label>

        <label class="application-filter-field">
          <span>投递结束日</span>
          <input
            v-model="filters.submitted_to"
            data-test="application-submitted-to"
            type="date"
          >
        </label>

        <label class="application-filter-field">
          <span>排序</span>
          <select
            v-model="filters.sort"
            data-test="application-sort-filter"
          >
            <option value="submitted_desc">投递时间倒序</option>
            <option value="submitted_asc">投递时间正序</option>
          </select>
        </label>

        <button
          class="application-filter-submit"
          type="submit"
          data-test="application-filter-submit"
          :disabled="isBusy"
        >
          <SlidersHorizontal :size="16" aria-hidden="true" />
          筛选申请
        </button>
      </form>

      <div
        v-if="displayError"
        class="applications-error"
        role="alert"
        aria-live="assertive"
      >
        <AlertCircle :size="18" aria-hidden="true" />
        <p>{{ displayError }}</p>
        <button
          type="button"
          data-test="applications-refresh"
          @click="loadApplications()"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          刷新申请
        </button>
      </div>

      <section
        class="applications-content"
        :aria-busy="pageLoading"
        aria-live="polite"
      >
        <div
          v-if="pageLoading && store.applications.length === 0"
          class="applications-state"
          data-test="applications-loading"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          <p>正在加载申请</p>
        </div>

        <div
          v-else-if="store.applications.length === 0"
          class="applications-state"
          data-test="applications-empty"
        >
          <ClipboardList :size="22" aria-hidden="true" />
          <p>暂无符合条件的申请</p>
        </div>

        <ul v-else class="application-list">
          <li
            v-for="application in store.applications"
            :key="application.application_id"
            class="application-row"
            :data-test="`application-row-${application.application_id}`"
          >
            <div class="application-row__identity">
              <h2 class="application-row__student">
                {{ application.student_name }}
              </h2>
              <p class="application-row__job">
                {{ application.job_title }}
              </p>
            </div>

            <div class="application-row__submitted">
              <span>投递时间</span>
              <time :datetime="application.submitted_at">
                {{ formatSubmittedAt(application.submitted_at) }}
              </time>
            </div>

            <div class="application-row__status">
              <EnterpriseApplicationStatusBadge
                :status="application.effective_status"
                :position-closed="application.position_closed"
              />
            </div>

            <RouterLink
              class="application-row__action"
              :to="applicationPath(application.application_id)"
              :data-test="`application-detail-${application.application_id}`"
            >
              查看详情
            </RouterLink>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<style scoped>
.enterprise-applications-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.enterprise-applications-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  overflow-x: clip;
}

.applications-heading {
  min-width: 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.applications-heading > span {
  color: var(--ark-signal);
  font-size: 0.7rem;
}

.applications-heading h1 {
  margin: 8px 0 0;
  font-size: 3rem;
  line-height: 1.02;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.applications-heading p {
  max-width: 66ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-filter-form {
  display: grid;
  grid-template-columns:
    minmax(160px, 1.3fr)
    minmax(120px, 0.8fr)
    minmax(140px, 0.8fr)
    minmax(140px, 0.8fr)
    minmax(150px, 0.9fr)
    auto;
  gap: 12px;
  align-items: end;
  min-width: 0;
  margin-top: 18px;
  padding: 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.application-filter-field {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.application-filter-field > span {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-filter-field select,
.application-filter-field input {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.application-filter-submit {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.applications-error {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.applications-error > p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.applications-error > button {
  display: inline-flex;
  min-width: 0;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 7px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.applications-error > button:hover,
.applications-error > button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.applications-content {
  min-width: 0;
  min-height: 320px;
  margin-top: 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.applications-state {
  display: grid;
  min-height: 320px;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 28px 18px;
  color: var(--ark-muted);
  text-align: center;
}

.applications-state p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-list {
  display: grid;
  gap: 1px;
  margin: 0;
  padding: 0;
  background: var(--ark-line);
  list-style: none;
}

.application-row {
  display: grid;
  grid-template-columns:
    minmax(0, 1.1fr)
    minmax(150px, 0.55fr)
    minmax(130px, auto)
    auto;
  gap: 18px;
  align-items: center;
  min-width: 0;
  padding: 18px 20px;
  background: var(--ark-surface-0);
}

.application-row__identity,
.application-row__submitted,
.application-row__status {
  min-width: 0;
}

.application-row__student {
  margin: 0;
  font-size: 1rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-row__job {
  margin: 5px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-row__submitted {
  display: grid;
  gap: 3px;
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.application-row__submitted time {
  color: var(--ark-paper);
  font-variant-numeric: tabular-nums;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.application-row__action {
  display: inline-flex;
  min-width: 0;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  padding: 7px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-decoration: none;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.application-row__action:hover,
.application-row__action:focus-visible {
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

@media (max-width: 900px) {
  .application-filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .application-filter-submit {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .enterprise-applications-main {
    padding: 28px 14px 48px;
  }

  .applications-heading h1 {
    font-size: 2.25rem;
  }

  .application-filter-form {
    grid-template-columns: minmax(0, 1fr);
    padding: 13px;
  }

  .application-filter-submit {
    grid-column: auto;
    width: 100%;
  }

  .applications-error {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .applications-error > button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .application-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
    padding: 16px;
  }

  .application-row__action {
    width: 100%;
  }
}
</style>
