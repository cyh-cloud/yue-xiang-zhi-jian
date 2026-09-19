<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  History,
  MessageSquare,
  RefreshCw,
  UserRound
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import type {
  ApplicationStatus,
  EnterpriseApplicationDetail
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import EnterpriseApplicationStatusBadge from '@/components/EnterpriseApplicationStatusBadge.vue'
import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

type ManualApplicationStatus = Exclude<ApplicationStatus, 'pending'>

const statusTargets: Array<{
  status: ManualApplicationStatus
  label: string
}> = [
  { status: 'viewed', label: '已查看' },
  { status: 'intent', label: '意向沟通' },
  { status: 'unsuitable', label: '不合适' }
]

const statusLabels: Record<ApplicationStatus | 'closed', string> = {
  pending: '待处理',
  viewed: '已查看',
  intent: '意向沟通',
  unsuitable: '不合适',
  closed: '岗位已关闭'
}

const snapshotFieldLabels: Record<string, string> = {
  education: '教育经历',
  experience: '实践经历',
  skills: '技能',
  items: '技能成果',
  title: '成果标题',
  outcome: '成果说明',
  company: '实践单位',
  responsibility: '实践内容'
}

const store = useEnterpriseConsoleStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const pageLoading = ref(false)
const pageError = ref('')

const applicationId = computed(() =>
  String(route.params.applicationId ?? '')
)
const application = computed<EnterpriseApplicationDetail | null>(() => {
  if (
    !store.activeApplication ||
    store.activeApplication.application_id !== applicationId.value
  ) {
    return null
  }
  return store.activeApplication
})
const displayError = computed(() => pageError.value || store.error)
const isBusy = computed(() => pageLoading.value || store.loading || store.saving)
const resumeEntries = computed(() =>
  application.value
    ? Object.entries(application.value.resume_snapshot)
    : []
)
const hasSkillProfile = computed(() => {
  const detail = application.value
  return Boolean(
    detail?.skill_profile_attached &&
      detail.skill_profile &&
      hasMeaningfulValue(detail.skill_profile)
  )
})
const skillProfileEntries = computed(() =>
  application.value?.skill_profile
    ? Object.entries(application.value.skill_profile)
    : []
)
const orderedStatusHistory = computed(() =>
  application.value
    ? [...application.value.status_history].sort(
        (left, right) => left.sequence_no - right.sequence_no
      )
    : []
)

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false
  }
  if (typeof value === 'string') {
    return value.trim().length > 0
  }
  if (typeof value === 'number') {
    return Number.isFinite(value)
  }
  if (typeof value === 'boolean') {
    return true
  }
  if (Array.isArray(value)) {
    return value.some(item => hasMeaningfulValue(item))
  }
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).some(item =>
      hasMeaningfulValue(item)
    )
  }
  return false
}

function snapshotFieldLabel(key: string): string {
  return snapshotFieldLabels[key] ?? key
}

function snapshotLeafValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '未填写'
  }
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value)
}

function formatSnapshotValue(value: unknown): string {
  if (Array.isArray(value)) {
    const values = value
      .map(item => snapshotLeafValue(item))
      .filter(item => item !== '未填写')
    return values.length ? values.join(', ') : '未填写'
  }
  return snapshotLeafValue(value)
}

function statusLabel(status: ApplicationStatus | 'closed'): string {
  return statusLabels[status]
}

function formatStatusTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date)
}

async function loadDetail() {
  if (!applicationId.value) {
    pageError.value = '申请不存在'
    return
  }

  pageLoading.value = true
  pageError.value = ''

  const loaded = await store.loadApplication(applicationId.value)
  if (!loaded) {
    pageError.value = store.error
  }

  pageLoading.value = false
}

async function changeStatus(status: ManualApplicationStatus) {
  const current = application.value
  if (!current || current.position_closed || store.saving) {
    return
  }

  pageError.value = ''
  const changed = await store.changeApplicationStatus(
    current.application_id,
    current.status_version,
    status
  )
  if (!changed) {
    pageError.value = store.error
    return
  }

  const refreshed = await store.loadApplication(current.application_id)
  if (!refreshed) {
    pageError.value = store.error
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadDetail()
})
</script>

<template>
  <div class="application-detail-page">
    <AppHeader
      source="live"
      :loading="isBusy"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EnterpriseConsoleNav />

    <main class="application-detail-main">
      <RouterLink class="application-detail-back" to="/enterprise/applications">
        <ArrowLeft :size="16" aria-hidden="true" />
        返回申请列表
      </RouterLink>

      <div
        v-if="displayError"
        class="application-detail-error"
        role="alert"
        aria-live="assertive"
      >
        <AlertCircle :size="18" aria-hidden="true" />
        <p>{{ displayError }}</p>
        <button
          type="button"
          data-test="application-detail-refresh"
          @click="loadDetail"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          刷新详情
        </button>
      </div>

      <div
        v-if="pageLoading && !application"
        class="application-detail-state"
        data-test="application-detail-loading"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        <p>正在加载申请详情</p>
      </div>

      <section
        v-else-if="application"
        class="application-detail-content"
        :aria-busy="pageLoading"
      >
        <header class="application-profile">
          <div class="application-profile__icon" aria-hidden="true">
            <UserRound :size="25" />
          </div>
          <div class="application-profile__copy">
            <span class="ark-data">APPLICATION / {{ application.application_id }}</span>
            <h1>{{ application.student_name }}</h1>
            <p>{{ application.job_title }}</p>
          </div>
          <div class="application-profile__facts">
            <div data-test="current-application-status">
              <EnterpriseApplicationStatusBadge
                :status="application.effective_status"
                :position-closed="application.position_closed"
              />
            </div>
            <time :datetime="application.submitted_at">
              投递于 {{ formatStatusTime(application.submitted_at) }}
            </time>
          </div>
        </header>

        <div class="application-detail-grid">
          <div class="application-detail-column">
            <section
              class="detail-section"
              data-test="resume-snapshot"
              aria-labelledby="resume-snapshot-title"
            >
              <header class="detail-section__heading">
                <div>
                  <span class="ark-data">FROZEN RESUME SNAPSHOT</span>
                  <h2 id="resume-snapshot-title">简历快照</h2>
                </div>
              </header>

              <dl class="resume-fields">
                <div
                  v-for="[key, value] in resumeEntries"
                  :key="key"
                  class="resume-field"
                >
                  <dt>{{ snapshotFieldLabel(key) }}</dt>
                  <dd>{{ formatSnapshotValue(value) }}</dd>
                </div>
              </dl>
            </section>

            <section
              v-if="hasSkillProfile"
              class="detail-section"
              data-test="skill-profile"
              aria-labelledby="skill-profile-title"
            >
              <header class="detail-section__heading">
                <div>
                  <span class="ark-data">ATTACHED SKILL PROFILE</span>
                  <h2 id="skill-profile-title">技能档案快照</h2>
                </div>
              </header>

              <dl class="resume-fields">
                <div
                  v-for="[key, value] in skillProfileEntries"
                  :key="key"
                  class="resume-field"
                >
                  <dt>{{ snapshotFieldLabel(key) }}</dt>
                  <dd>{{ formatSnapshotValue(value) }}</dd>
                </div>
              </dl>
            </section>

            <p
              v-else
              class="skill-profile-empty"
              data-test="skill-profile-empty"
            >
              未附带技能档案
            </p>
          </div>

          <div class="application-detail-column">
            <section
              class="detail-section"
              data-test="status-history"
              aria-labelledby="status-history-title"
            >
              <header class="detail-section__heading">
                <div>
                  <span class="ark-data">STATUS HISTORY</span>
                  <h2 id="status-history-title">状态记录</h2>
                </div>
                <History :size="19" aria-hidden="true" />
              </header>

              <ol v-if="orderedStatusHistory.length" class="status-history">
                <li
                  v-for="item in orderedStatusHistory"
                  :key="item.sequence_no"
                  data-test="status-history-item"
                >
                  <span class="status-history__sequence ark-data">
                    {{ String(item.sequence_no).padStart(2, '0') }}
                  </span>
                  <div>
                    <p>
                      <span>{{ statusLabel(item.previous_status) }}</span>
                      <span aria-hidden="true"> → </span>
                      <strong>{{ statusLabel(item.new_status) }}</strong>
                    </p>
                    <time :datetime="item.created_at">
                      {{ formatStatusTime(item.created_at) }}
                    </time>
                  </div>
                </li>
              </ol>
              <p v-else class="status-history-empty">暂无状态记录</p>
            </section>

            <section
              class="detail-section status-actions-section"
              aria-labelledby="status-actions-title"
            >
              <header class="detail-section__heading">
                <div>
                  <span class="ark-data">MANUAL MARKING</span>
                  <h2 id="status-actions-title">标记申请状态</h2>
                </div>
              </header>

              <p
                v-if="application.position_closed"
                class="status-actions-note"
              >
                岗位已关闭，历史状态仅供查看，不能再改标。
              </p>

              <div class="application-status-controls">
                <button
                  v-for="target in statusTargets"
                  :key="target.status"
                  type="button"
                  :data-status="target.status"
                  :data-test="`application-status-${target.status}`"
                  :aria-pressed="application.status === target.status"
                  :disabled="application.position_closed || store.saving"
                  @click="changeStatus(target.status)"
                >
                  {{ target.label }}
                </button>
              </div>

              <RouterLink
                v-if="application"
                class="message-applicant"
                data-test="message-applicant"
                to="/messages"
              >
                <MessageSquare :size="17" aria-hidden="true" />
                私信沟通
              </RouterLink>
            </section>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.application-detail-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.application-detail-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 36px 24px 72px;
  overflow-x: clip;
}

.application-detail-back {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  gap: 7px;
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-decoration: none;
  text-wrap: pretty;
  word-break: normal;
}

.application-detail-back:hover,
.application-detail-back:focus-visible {
  color: var(--ark-signal);
}

.application-detail-error {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.application-detail-error > p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-detail-error > button {
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

.application-detail-error > button:hover,
.application-detail-error > button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-detail-state {
  display: grid;
  min-height: 360px;
  place-items: center;
  align-content: center;
  gap: 10px;
  margin-top: 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.application-detail-content {
  min-width: 0;
  margin-top: 14px;
}

.application-profile {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) minmax(210px, auto);
  gap: 16px;
  align-items: center;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.application-profile__icon {
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.application-profile__copy,
.application-profile__facts {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.application-profile__copy > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.application-profile h1 {
  margin: 5px 0 0;
  font-size: 2.1rem;
  line-height: 1.15;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-profile__copy p {
  margin: 7px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-profile__facts {
  display: grid;
  justify-items: end;
  gap: 8px;
  text-align: right;
}

.application-profile__facts > time {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 12px;
  align-items: start;
  margin-top: 12px;
}

.application-detail-column {
  display: grid;
  min-width: 0;
  gap: 12px;
}

.detail-section {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.detail-section__heading {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.detail-section__heading h2 {
  margin: 3px 0 0;
  font-size: 1rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.detail-section__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.detail-section__heading > div > span {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.resume-fields {
  display: grid;
  margin: 0;
}

.resume-field {
  display: grid;
  grid-template-columns: minmax(100px, 0.32fr) minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
  padding: 14px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.resume-field:last-child {
  border-bottom: 0;
}

.resume-field dt,
.resume-field dd {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-field dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.resume-field dd {
  margin: 0;
  font-size: 0.84rem;
}

.skill-profile-empty {
  min-height: 74px;
  margin: 0;
  padding: 22px 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.status-history {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.status-history li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  padding: 13px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.status-history li:last-child {
  border-bottom: 0;
}

.status-history__sequence {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.status-history li > div {
  min-width: 0;
}

.status-history p,
.status-history time {
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.status-history p {
  margin: 0;
  font-size: 0.82rem;
}

.status-history strong {
  color: var(--ark-signal);
}

.status-history time {
  display: block;
  margin-top: 3px;
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.status-history-empty {
  margin: 0;
  padding: 22px 16px;
  color: var(--ark-muted);
  text-align: center;
}

.status-actions-note {
  margin: 0;
  padding: 13px 16px 0;
  color: var(--ark-state);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-status-controls {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
}

.application-status-controls button {
  display: inline-flex;
  min-width: 112px;
  min-height: 40px;
  flex: 1 1 112px;
  align-items: center;
  justify-content: center;
  padding: 8px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.application-status-controls button:hover:not(:disabled),
.application-status-controls button:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-status-controls button[aria-pressed="true"] {
  border-color: var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.application-status-controls button:disabled {
  border-color: var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  opacity: 1;
}

.message-applicant {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin: 0 16px 16px;
  padding: 8px 13px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  color: var(--ark-signal);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-decoration: none;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.message-applicant:hover,
.message-applicant:focus-visible {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
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
  .application-profile {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .application-profile__facts {
    grid-column: 1 / -1;
    justify-items: start;
    text-align: left;
  }

  .application-detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .application-detail-main {
    padding: 28px 14px 48px;
  }

  .application-detail-error {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .application-detail-error > button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .application-profile {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .application-profile h1 {
    font-size: 1.65rem;
  }

  .application-profile__icon {
    width: 46px;
    height: 46px;
  }

  .resume-field {
    grid-template-columns: minmax(0, 1fr);
    gap: 5px;
  }

  .application-status-controls {
    padding: 13px;
  }

  .application-status-controls button {
    flex-basis: 100%;
  }

  .message-applicant {
    width: calc(100% - 26px);
    margin-inline: 13px;
  }
}
</style>
