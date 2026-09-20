<script setup lang="ts">
import {
  AlertCircle,
  ClipboardList,
  RefreshCw
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import JobMatchingStatusBadge from '@/components/JobMatchingStatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useJobMatchingStore } from '@/stores/jobMatching'

const auth = useAuthStore()
const router = useRouter()
const store = useJobMatchingStore()

const showInitialLoading = computed(
  () => store.loading && store.applications.length === 0
)
const showInitialError = computed(
  () =>
    !store.loading &&
    store.applications.length === 0 &&
    store.error.length > 0
)

const submittedAtFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23'
})

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

async function loadApplications() {
  await store.loadApplications()
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadApplications()
})
</script>

<template>
  <div class="applications-page">
    <AppHeader
      source="live"
      :loading="store.loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <JobMatchingNav />

    <main class="applications-main">
      <header class="applications-heading">
        <h1>我的投递</h1>
        <p>查看全部历史申请及由招聘企业维护的最新处理状态。</p>
      </header>

      <section
        v-if="showInitialLoading"
        class="applications-state"
        data-test="applications-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="21" aria-hidden="true" />
        <p>正在加载投递记录</p>
      </section>

      <section
        v-else-if="showInitialError"
        class="applications-state is-error"
        data-test="applications-error"
        role="alert"
      >
        <AlertCircle :size="21" aria-hidden="true" />
        <p>{{ store.error }}</p>
        <button type="button" @click="loadApplications">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>

      <template v-else>
        <div
          v-if="store.error"
          class="applications-notice is-error"
          role="alert"
        >
          <AlertCircle :size="17" aria-hidden="true" />
          <p>{{ store.error }}</p>
          <button type="button" @click="loadApplications">
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </div>

        <section
          class="applications-content"
          aria-labelledby="application-list-title"
        >
          <h2 id="application-list-title" class="ark-sr-only">
            投递记录
          </h2>

          <div
            v-if="store.applications.length === 0"
            class="applications-empty"
            data-test="applications-empty"
          >
            <ClipboardList :size="23" aria-hidden="true" />
            <p>暂无投递记录</p>
          </div>

          <ol v-else class="application-list">
            <li
              v-for="application in store.applications"
              :key="application.application_id"
              class="application-item"
              data-test="application-item"
              :data-application-id="application.application_id"
            >
              <div class="application-item__identity">
                <h2>{{ application.job_title }}</h2>
                <p>{{ application.enterprise_name }}</p>
              </div>

              <div class="application-item__submitted">
                <span>投递时间</span>
                <time :datetime="application.submitted_at">
                  {{ formatSubmittedAt(application.submitted_at) }}
                </time>
              </div>

              <div class="application-item__status">
                <span class="application-item__status-label">当前状态</span>
                <JobMatchingStatusBadge
                  :status="application.status"
                  :effective-status="application.effective_status"
                  :position-closed="application.position_closed"
                />
              </div>
            </li>
          </ol>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.applications-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.applications-main {
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

.applications-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.04;
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

.applications-state {
  display: grid;
  min-height: 300px;
  place-items: center;
  align-content: center;
  gap: 10px;
  margin-top: 18px;
  padding: 28px 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: center;
}

.applications-state p,
.applications-notice p,
.applications-empty p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.applications-state.is-error {
  color: var(--ark-signal);
}

.applications-state button,
.applications-notice button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.applications-state button:hover,
.applications-state button:focus-visible,
.applications-notice button:hover,
.applications-notice button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.applications-notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.applications-notice.is-error {
  color: var(--ark-signal);
}

.applications-content {
  min-width: 0;
  margin-top: 18px;
}

.applications-empty {
  display: grid;
  min-height: 220px;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 28px 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: center;
}

.application-list {
  display: grid;
  gap: 1px;
  min-width: 0;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
  list-style: none;
}

.application-item {
  display: grid;
  grid-template-columns:
    minmax(0, 1.4fr)
    minmax(160px, 0.6fr)
    minmax(170px, auto);
  gap: 20px;
  align-items: center;
  min-width: 0;
  min-height: 116px;
  padding: 20px;
  background: var(--ark-surface-0);
}

.application-item__identity,
.application-item__submitted,
.application-item__status {
  min-width: 0;
}

.application-item__identity h2 {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-item__identity p {
  margin: 5px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-item__submitted {
  display: grid;
  gap: 3px;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  word-break: keep-all;
}

.application-item__submitted time {
  color: var(--ark-paper);
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.application-item__status {
  display: grid;
  justify-items: start;
  gap: 5px;
}

.application-item__status-label {
  color: var(--ark-muted);
  font-size: 0.68rem;
  line-break: strict;
  word-break: keep-all;
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
  .applications-main {
    padding: 28px 14px 48px;
  }

  .applications-heading h1 {
    font-size: 2.25rem;
  }

  .applications-notice {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .applications-notice button {
    grid-column: 1 / -1;
    width: 100%;
  }

  .application-item {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
    padding: 17px;
  }
}

@media (max-width: 360px) {
  .applications-main {
    padding-inline: 12px;
  }

  .application-item {
    padding: 15px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
