<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  BriefcaseBusiness,
  Pencil,
  Plus,
  RefreshCw,
  Trash2
} from 'lucide-vue-next'
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import type {
  ApiFieldErrors,
  EnterpriseJob,
  EnterpriseJobPayload,
  JobReviewStatus
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import EnterpriseJobForm from '@/components/EnterpriseJobForm.vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

interface JobTab {
  value: JobReviewStatus | 'all'
  label: string
}

const jobTabs: JobTab[] = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' }
]

const statusLabels: Record<JobReviewStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回'
}

const store = useEnterpriseConsoleStore()
const auth = useAuthStore()
const router = useRouter()
const formOpen = ref(false)
const editingJob = ref<EnterpriseJob | null>(null)
const form = ref<EnterpriseJobPayload>(emptyPayload())
const fieldErrors = ref<ApiFieldErrors>({})
const pageError = ref('')
const pageLoading = ref(false)

const displayError = computed(() => pageError.value || store.error)
const isSaving = computed(() => store.saving)
const jobCategories = computed(() =>
  store.jobCategories.filter(category => category.group_key === 'job')
)
const fieldElementIds: Record<keyof EnterpriseJobPayload, string> = {
  title: 'job-title',
  salary: 'job-salary',
  location: 'job-location',
  category_id: 'job-category-select',
  description: 'job-description'
}

function emptyPayload(): EnterpriseJobPayload {
  return {
    title: '',
    salary: '',
    location: '',
    category_id: 0,
    description: ''
  }
}

function payloadFromJob(job: EnterpriseJob): EnterpriseJobPayload {
  return {
    title: job.title,
    salary: job.salary,
    location: job.location,
    category_id: job.category_id,
    description: job.description
  }
}

function normalizePayload(payload: EnterpriseJobPayload): EnterpriseJobPayload {
  return {
    title: payload.title.trim(),
    salary: payload.salary.trim(),
    location: payload.location.trim(),
    category_id: Number(payload.category_id),
    description: payload.description.trim()
  }
}

function validateJob(payload: EnterpriseJobPayload): ApiFieldErrors {
  const errors: ApiFieldErrors = {}

  if (!payload.title) {
    errors.title = '请填写职位标题'
  }
  if (!payload.salary) {
    errors.salary = '请填写薪资'
  }
  if (!payload.location) {
    errors.location = '请填写工作地点'
  }
  if (!payload.category_id) {
    errors.category_id = '请选择职位类别'
  }
  if (!payload.description) {
    errors.description = '请填写职位描述'
  }

  return errors
}

function resetForm() {
  form.value = emptyPayload()
  fieldErrors.value = {}
}

async function loadInitialJobs() {
  pageLoading.value = true
  pageError.value = ''
  fieldErrors.value = {}

  const categoriesLoaded = await store.loadJobCategories()
  const categoriesError = categoriesLoaded ? '' : store.error
  const jobsLoaded = await store.loadJobs(store.jobReviewFilter)
  const jobsError = jobsLoaded ? '' : store.error

  pageError.value = categoriesError || jobsError
  pageLoading.value = false
}

async function selectJobTab(status: JobReviewStatus | 'all') {
  pageError.value = ''
  const loaded = await store.loadJobs(status)
  if (!loaded) {
    pageError.value = store.error
  }
}

function openCreateForm() {
  editingJob.value = null
  resetForm()
  formOpen.value = true
}

async function openEditForm(job: EnterpriseJob) {
  editingJob.value = job
  form.value = payloadFromJob(job)
  fieldErrors.value = {}
  formOpen.value = true
  await nextTick()
  document.getElementById('job-title')?.focus()
}

function closeForm() {
  formOpen.value = false
  editingJob.value = null
  resetForm()
}

async function focusFirstError(errors: ApiFieldErrors) {
  await nextTick()
  const firstField = Object.keys(errors)[0]
  if (firstField) {
    document
      .getElementById(fieldElementIds[firstField as keyof EnterpriseJobPayload])
      ?.focus()
  }
}

async function submitJob() {
  form.value = normalizePayload(form.value)
  fieldErrors.value = validateJob(form.value)
  if (Object.keys(fieldErrors.value).length) {
    await focusFirstError(fieldErrors.value)
    return
  }

  pageError.value = ''
  const result = editingJob.value
    ? await store.editJob(
        editingJob.value.job_id,
        editingJob.value.version,
        form.value
      )
    : await store.createJob(form.value)

  if (result) {
    formOpen.value = false
    editingJob.value = null
    resetForm()
    return
  }

  pageError.value = store.error
}

async function deleteJob(job: EnterpriseJob) {
  if (
    !window.confirm(
      `确认删除职位“${job.title}”？删除后将不再出现在当前职位列表中。`
    )
  ) {
    return
  }

  pageError.value = ''
  const deleted = await store.deleteJob(job)
  if (!deleted) {
    pageError.value = store.error
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadInitialJobs()
})
</script>

<template>
  <div class="enterprise-jobs-page">
    <AppHeader
      source="live"
      :loading="pageLoading || store.loading || store.saving"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EnterpriseConsoleNav />

    <main class="enterprise-jobs-main">
      <header class="enterprise-jobs-heading">
        <RouterLink data-test="jobs-back" to="/enterprise">
          <ArrowLeft :size="16" aria-hidden="true" />
          返回企业看板
        </RouterLink>
        <span class="ark-data">09 / ENTERPRISE JOBS</span>
        <div class="enterprise-jobs-heading__row">
          <div>
            <h1>职位管理</h1>
            <p>
              管理本企业职位内容与审核状态。编辑已通过职位后会重新进入待审核。
            </p>
          </div>
          <button
            type="button"
            data-test="job-create-toggle"
            :aria-expanded="formOpen"
            @click="openCreateForm"
          >
            <Plus :size="17" aria-hidden="true" />
            发布职位
          </button>
        </div>
      </header>

      <nav class="job-filters" aria-label="职位审核状态筛选">
        <button
          v-for="tab in jobTabs"
          :key="tab.value"
          type="button"
          class="job-filter-tab"
          :class="{ 'is-active': store.jobReviewFilter === tab.value }"
          :data-test="`job-filter-${tab.value}`"
          :aria-pressed="store.jobReviewFilter === tab.value"
          :disabled="store.loading"
          @click="selectJobTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div
        v-if="displayError"
        class="enterprise-jobs-error"
        role="alert"
        aria-live="assertive"
      >
        <AlertCircle :size="18" aria-hidden="true" />
        <p>{{ displayError }}</p>
        <button type="button" data-test="jobs-refresh" @click="loadInitialJobs">
          <RefreshCw :size="16" aria-hidden="true" />
          刷新职位
        </button>
      </div>

      <section v-if="formOpen" class="enterprise-jobs-form">
        <EnterpriseJobForm
          v-model="form"
          :categories="jobCategories"
          :editing="Boolean(editingJob)"
          :saving="isSaving"
          :field-errors="fieldErrors"
          @submit="submitJob"
          @cancel="closeForm"
        />
      </section>

      <section
        class="enterprise-jobs-content"
        :aria-busy="pageLoading"
        aria-live="polite"
      >
        <div
          v-if="pageLoading && store.jobs.length === 0"
          data-test="jobs-loading"
          class="enterprise-jobs-state"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          <p>正在加载职位</p>
        </div>

        <div
          v-else-if="store.jobs.length === 0"
          data-test="jobs-empty"
          class="enterprise-jobs-state"
        >
          <BriefcaseBusiness :size="22" aria-hidden="true" />
          <p>暂无职位</p>
          <span>可发布职位并提交审核。</span>
        </div>

        <ul v-else class="job-list">
          <li
            v-for="job in store.jobs"
            :key="job.job_id"
            :data-test="`job-${job.job_id}`"
            class="job-row"
          >
            <div class="job-row__body">
              <div class="job-row__top">
                <div class="job-row__copy">
                  <h2 class="job-row__title">{{ job.title }}</h2>
                  <div class="job-row__meta">
                    <span>{{ job.salary }}</span>
                    <span>{{ job.location }}</span>
                    <span>{{ job.category_name }}</span>
                  </div>
                </div>
                <span
                  class="job-status"
                  :class="`job-status--${job.review_status}`"
                  :data-status="job.review_status"
                  :data-test="`job-status-${job.review_status}`"
                >
                  {{ statusLabels[job.review_status] }}
                </span>
              </div>

              <p class="job-row__description">{{ job.description }}</p>

              <div
                v-if="
                  job.review_status === 'rejected' && job.rejection_opinion
                "
                class="job-rejection"
                data-test="job-rejection-opinion"
              >
                <strong>驳回意见</strong>
                <p>{{ job.rejection_opinion }}</p>
              </div>
            </div>

            <div class="job-row__actions">
              <button
                type="button"
                :aria-label="`编辑职位：${job.title}`"
                :data-test="`job-edit-${job.job_id}`"
                @click="openEditForm(job)"
              >
                <Pencil :size="16" aria-hidden="true" />
                编辑
              </button>
              <button
                type="button"
                :aria-label="`删除职位：${job.title}`"
                :data-test="`job-delete-${job.job_id}`"
                @click="deleteJob(job)"
              >
                <Trash2 :size="16" aria-hidden="true" />
                删除
              </button>
            </div>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<style scoped>
.enterprise-jobs-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.enterprise-jobs-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  overflow-x: clip;
}

.enterprise-jobs-heading {
  min-width: 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.enterprise-jobs-heading > a {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 40px;
  margin-bottom: 16px;
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-decoration: none;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-jobs-heading > a:hover,
.enterprise-jobs-heading > a:focus-visible {
  color: var(--ark-signal);
}

.enterprise-jobs-heading > span {
  color: var(--ark-signal);
  font-size: 0.7rem;
}

.enterprise-jobs-heading__row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-top: 8px;
}

.enterprise-jobs-heading__row > div {
  min-width: 0;
}

.enterprise-jobs-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: balance;
  word-break: normal;
}

.enterprise-jobs-heading > p {
  max-width: 64ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-jobs-heading__row > button {
  display: inline-flex;
  flex: 0 1 auto;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 42px;
  padding: 8px 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.job-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
  margin-top: 18px;
}

.job-filter-tab {
  flex: 1 1 128px;
  min-width: 0;
  min-height: 40px;
  padding: 7px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.job-filter-tab:hover:not(:disabled),
.job-filter-tab:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.job-filter-tab.is-active {
  border-color: var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
  font-weight: 700;
}

.enterprise-jobs-error {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.enterprise-jobs-error > p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-jobs-error > button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 7px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.enterprise-jobs-error > button:hover,
.enterprise-jobs-error > button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.enterprise-jobs-form {
  margin-top: 12px;
}

.enterprise-jobs-content {
  min-width: 0;
  min-height: 320px;
  margin-top: 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.enterprise-jobs-state {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  min-height: 320px;
  padding: 28px 18px;
  color: var(--ark-muted);
  text-align: center;
}

.enterprise-jobs-state p,
.enterprise-jobs-state span {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.job-list {
  display: grid;
  gap: 1px;
  margin: 0;
  padding: 0;
  background: var(--ark-line);
  list-style: none;
}

.job-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 20px;
  align-items: start;
  min-width: 0;
  padding: 20px;
  background: var(--ark-surface-0);
}

.job-row__body,
.job-row__copy,
.job-row__top {
  min-width: 0;
}

.job-row__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.job-row__title {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.4;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.job-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  min-width: 0;
  margin-top: 7px;
  color: var(--ark-muted);
  font-size: 0.8rem;
}

.job-row__meta span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.job-status {
  display: inline-flex;
  flex: 0 1 auto;
  align-items: center;
  min-height: 32px;
  max-width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.job-status--approved {
  color: var(--ark-state);
}

.job-status--rejected {
  color: var(--ark-signal);
}

.job-row__description {
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.job-rejection {
  margin-top: 12px;
  padding: 11px 12px;
  border-left: 2px solid var(--ark-signal);
  background: var(--ark-surface-1);
}

.job-rejection strong {
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.job-rejection p {
  margin: 4px 0 0;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.job-row__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.job-row__actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 7px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.job-row__actions button:hover,
.job-row__actions button:focus-visible {
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

@media (max-width: 720px) {
  .enterprise-jobs-main {
    padding: 28px 14px 48px;
  }

  .enterprise-jobs-heading__row {
    align-items: stretch;
    flex-direction: column;
    gap: 16px;
  }

  .enterprise-jobs-heading h1 {
    font-size: 2.25rem;
  }

  .enterprise-jobs-heading__row > button {
    width: 100%;
  }

  .job-filter-tab {
    flex-basis: 120px;
  }

  .enterprise-jobs-error {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .enterprise-jobs-error > button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .job-row {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .job-row__top {
    flex-direction: column;
    gap: 10px;
  }

  .job-row__actions {
    justify-content: stretch;
  }

  .job-row__actions button {
    flex: 1 1 120px;
  }
}
</style>
