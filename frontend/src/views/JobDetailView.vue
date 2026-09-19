<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  Bookmark,
  BriefcaseBusiness,
  RefreshCw,
  Send
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useJobMatchingStore } from '@/stores/jobMatching'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const store = useJobMatchingStore()

const attachSkillProfile = ref(false)
const favoriteActionJobId = ref('')
const jobId = computed(() => {
  const value = route.params.jobId
  return Array.isArray(value) ? value[0] ?? '' : String(value ?? '')
})
const activeJob = computed(() =>
  store.activeJob?.job_id === jobId.value ? store.activeJob : null
)
const showInitialLoading = computed(
  () => store.loading && activeJob.value === null
)
const unavailableMessage = computed(
  () => store.error || '岗位已关闭或暂不可投递'
)

async function loadJob() {
  if (!jobId.value) {
    return
  }
  attachSkillProfile.value = false
  const loaded = await store.loadJob(jobId.value)
  if (loaded) {
    await store.loadFavorites()
  }
}

function isFavorite(jobId: string): boolean {
  return store.favorites.some(favorite => favorite.job_id === jobId)
}

async function toggleFavorite() {
  const job = activeJob.value
  if (!job || favoriteActionJobId.value || store.saving) {
    return
  }

  favoriteActionJobId.value = job.job_id
  try {
    if (isFavorite(job.job_id)) {
      await store.removeFavorite(job.job_id)
    } else {
      await store.addFavorite(job.job_id)
    }
  } finally {
    favoriteActionJobId.value = ''
  }
}

async function submitApplication() {
  if (!activeJob.value || store.saving) {
    return
  }

  const application = await store.submitApplication(
    activeJob.value.job_id,
    attachSkillProfile.value
  )
  if (application) {
    await router.push('/student/employment/applications')
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

watch(jobId, () => void loadJob(), { immediate: true })
</script>

<template>
  <div class="job-detail-page">
    <AppHeader
      source="live"
      :loading="store.loading || store.saving"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <JobMatchingNav />

    <main class="job-detail-main">
      <section
        v-if="showInitialLoading"
        class="job-detail-state"
        data-test="job-detail-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="21" aria-hidden="true" />
        <p>正在加载岗位详情</p>
      </section>

      <section
        v-else-if="!activeJob"
        class="job-detail-state is-error"
        data-test="job-detail-unavailable"
        role="alert"
      >
        <AlertCircle :size="21" aria-hidden="true" />
        <p>{{ unavailableMessage }}</p>
        <RouterLink to="/student/employment/jobs">
          <ArrowLeft :size="16" aria-hidden="true" />
          返回岗位浏览
        </RouterLink>
      </section>

      <template v-else>
        <header class="job-detail-heading">
          <div class="job-detail-shell">
            <RouterLink
              class="job-detail-heading__back"
              to="/student/employment/jobs"
            >
              <ArrowLeft :size="16" aria-hidden="true" />
              返回岗位浏览
            </RouterLink>

            <div class="job-detail-heading__identity">
              <span class="job-detail-heading__icon" aria-hidden="true">
                <BriefcaseBusiness :size="24" />
              </span>
              <div>
                <h1>{{ activeJob.title }}</h1>
                <p>{{ activeJob.enterprise_name }}</p>
              </div>
            </div>
          </div>
        </header>

        <div class="job-detail-shell">
          <section
            v-if="store.error || store.errorCode === 'resume_required'"
            class="job-detail-notice is-error"
            role="alert"
          >
            <AlertCircle :size="17" aria-hidden="true" />
            <div>
              <p data-test="application-error">{{ store.error }}</p>
              <RouterLink
                v-if="store.errorCode === 'resume_required'"
                data-test="create-resume-link"
                to="/student/employment/resume"
              >
                前往简历维护
                <Send :size="15" aria-hidden="true" />
              </RouterLink>
            </div>
          </section>

          <div class="job-detail-layout">
            <article class="job-detail" data-test="job-detail">
              <header class="job-detail__title">
                <span class="ark-data">
                  {{ activeJob.category_name }}
                </span>
                <h2>岗位详情</h2>
              </header>

              <dl class="job-detail__facts">
                <div>
                  <dt>公司</dt>
                  <dd>{{ activeJob.enterprise_name }}</dd>
                </div>
                <div>
                  <dt>薪资</dt>
                  <dd class="ark-data">{{ activeJob.salary }}</dd>
                </div>
                <div>
                  <dt>地点</dt>
                  <dd>{{ activeJob.location }}</dd>
                </div>
              </dl>

              <section
                class="job-detail__description"
                aria-labelledby="job-description-title"
              >
                <h2 id="job-description-title">岗位描述</h2>
                <p data-test="job-description">
                  {{ activeJob.description }}
                </p>
              </section>
            </article>

            <aside
              class="application-panel"
              aria-labelledby="application-panel-title"
            >
              <h2 id="application-panel-title">申请岗位</h2>
              <p>投递后可在“我的投递”查看处理状态。</p>

              <button
                class="application-panel__favorite"
                :class="{
                  'is-active': isFavorite(activeJob.job_id)
                }"
                type="button"
                data-test="favorite-toggle"
                :aria-pressed="isFavorite(activeJob.job_id)"
                :disabled="
                  Boolean(favoriteActionJobId) || store.saving
                "
                @click="toggleFavorite"
              >
                <RefreshCw
                  v-if="favoriteActionJobId === activeJob.job_id"
                  class="spinning"
                  :size="16"
                  aria-hidden="true"
                />
                <Bookmark v-else :size="16" aria-hidden="true" />
                {{
                  isFavorite(activeJob.job_id)
                    ? '取消收藏'
                    : '收藏岗位'
                }}
              </button>

              <form
                class="application-form"
                data-test="application-form"
                @submit.prevent="submitApplication"
              >
                <label class="application-form__attachment">
                  <input
                    v-model="attachSkillProfile"
                    data-test="attach-skill-profile"
                    type="checkbox"
                  >
                  <span>附带技能档案</span>
                </label>

                <button
                  data-test="submit-application"
                  type="submit"
                  :disabled="store.saving"
                >
                  <RefreshCw
                    v-if="store.saving"
                    class="spinning"
                    :size="17"
                    aria-hidden="true"
                  />
                  <Send v-else :size="17" aria-hidden="true" />
                  <span>投递简历</span>
                </button>
              </form>
            </aside>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.job-detail-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.job-detail-main {
  min-width: 0;
  padding-bottom: 72px;
}

.job-detail-shell {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding-inline: 24px;
}

.job-detail-state {
  display: grid;
  min-height: 360px;
  place-items: center;
  align-content: center;
  gap: 10px;
  margin: 24px;
  padding: 24px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  text-align: center;
}

.job-detail-state p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-detail-state.is-error {
  color: var(--ark-signal);
}

.job-detail-state a,
.job-detail-heading__back {
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
  text-decoration: none;
  word-break: keep-all;
}

.job-detail-state a:hover,
.job-detail-state a:focus-visible,
.job-detail-heading__back:hover,
.job-detail-heading__back:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.job-detail-heading {
  border-bottom: 1px solid var(--ark-line-strong);
}

.job-detail-heading .job-detail-shell {
  padding-top: 28px;
  padding-bottom: 26px;
}

.job-detail-heading__back {
  width: fit-content;
  margin-bottom: 20px;
  background: transparent;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.job-detail-heading__identity {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 15px;
  align-items: start;
  min-width: 0;
}

.job-detail-heading__icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.job-detail-heading__identity > div {
  min-width: 0;
}

.job-detail-heading h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1.08;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.job-detail-heading p {
  margin: 7px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-detail-notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: 18px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.job-detail-notice > div {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.job-detail-notice p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-detail-notice a {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 6px;
  color: var(--ark-signal);
  font-size: 0.8rem;
  line-break: strict;
  word-break: keep-all;
}

.job-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(270px, 0.75fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
  margin-top: 18px;
}

.job-detail,
.application-panel {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.job-detail {
  padding: 24px;
}

.job-detail__title > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
  line-break: strict;
  word-break: keep-all;
}

.job-detail__title h2,
.job-detail__description h2,
.application-panel h2 {
  margin: 6px 0 0;
  font-size: 1.08rem;
  line-height: 1.35;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.job-detail__facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 20px 0 0;
  background: var(--ark-line);
}

.job-detail__facts > div {
  min-width: 0;
  padding: 13px;
  background: var(--ark-surface-1);
}

.job-detail__facts dt,
.job-detail__facts dd {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.job-detail__facts dt {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.job-detail__facts dd {
  margin: 4px 0 0;
  font-size: 0.86rem;
}

.job-detail__description {
  margin-top: 26px;
  padding-top: 20px;
  border-top: 1px solid var(--ark-line);
}

.job-detail__description p {
  max-width: 72ch;
  margin: 10px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: pre-line;
  word-break: normal;
}

.application-panel {
  padding: 22px;
}

.application-panel > p {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.application-panel__favorite {
  display: inline-flex;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin-top: 16px;
  padding: 8px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  line-break: strict;
  text-align: center;
  word-break: keep-all;
}

.application-panel__favorite:hover:not(:disabled),
.application-panel__favorite:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-panel__favorite.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-form {
  display: grid;
  gap: 14px;
  min-width: 0;
  margin-top: 20px;
}

.application-form__attachment {
  display: flex;
  min-width: 0;
  min-height: 48px;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  cursor: pointer;
  line-break: strict;
  word-break: keep-all;
}

.application-form__attachment:hover,
.application-form__attachment:focus-within {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.application-form__attachment input {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  margin: 0;
  accent-color: var(--ark-signal);
}

.application-form button {
  display: inline-flex;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 16px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  line-break: strict;
  text-align: center;
  word-break: keep-all;
}

.application-form button:hover:not(:disabled),
.application-form button:focus-visible:not(:disabled) {
  background: var(--ark-surface-0);
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

@media (max-width: 860px) {
  .job-detail-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .job-detail-main {
    padding-bottom: 48px;
  }

  .job-detail-shell {
    padding-inline: 14px;
  }

  .job-detail-state {
    margin-inline: 14px;
  }

  .job-detail-heading h1 {
    font-size: 1.95rem;
  }

  .job-detail__facts {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 360px) {
  .job-detail-shell {
    padding-inline: 12px;
  }

  .job-detail-heading__identity {
    grid-template-columns: minmax(0, 1fr);
  }

  .job-detail-heading__icon {
    width: 42px;
    height: 42px;
  }

  .job-detail,
  .application-panel {
    padding: 17px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
