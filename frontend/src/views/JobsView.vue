<script setup lang="ts">
import {
  AlertCircle,
  ArrowRight,
  Bookmark,
  BriefcaseBusiness,
  RefreshCw
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { JobMatchingJob } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useJobMatchingStore } from '@/stores/jobMatching'

const auth = useAuthStore()
const router = useRouter()
const store = useJobMatchingStore()
const favoriteActionJobId = ref('')

const hasJobs = computed(
  () => store.jobs.length > 0 || store.recommendedJobs.length > 0
)
const showInitialLoading = computed(
  () => store.loading && !hasJobs.value
)
const showInitialError = computed(
  () => !store.loading && !hasJobs.value && store.error.length > 0
)

const sections = computed(() => [
  {
    key: 'recommended',
    test: 'recommended-jobs',
    title: '推荐岗位',
    description: '根据岗位兴趣与近期学习情况形成',
    empty: '暂无推荐',
    jobs: store.recommendedJobs.filter(
      job => job.review_status === 'approved'
    ),
    gridClass: 'recommended-grid',
    recommended: true
  },
  {
    key: 'all',
    test: 'all-jobs',
    title: '全部岗位',
    description: '当前全部已上架岗位',
    empty: '暂无岗位',
    jobs: store.jobs.filter(job => job.review_status === 'approved'),
    gridClass: 'job-list',
    recommended: false
  }
])

async function loadJobs() {
  const loaded = await store.loadJobs()
  if (loaded) {
    await store.loadFavorites()
  }
}

function isFavorite(jobId: string): boolean {
  return store.favorites.some(favorite => favorite.job_id === jobId)
}

async function toggleFavorite(job: JobMatchingJob) {
  if (favoriteActionJobId.value || store.saving) {
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

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadJobs()
})
</script>

<template>
  <div class="jobs-page">
    <AppHeader
      source="live"
      :loading="store.loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <JobMatchingNav />

    <main class="jobs-main">
      <header class="jobs-intro">
        <div class="jobs-shell">
          <h1>岗位浏览</h1>
          <p>
            查看推荐岗位与全部已上架岗位，进入详情后可直接投递。
          </p>
        </div>
      </header>

      <section
        v-if="showInitialLoading"
        class="jobs-state"
        data-test="jobs-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="21" aria-hidden="true" />
        <p>正在加载岗位</p>
      </section>

      <section
        v-else-if="showInitialError"
        class="jobs-state is-error"
        data-test="jobs-error"
        role="alert"
      >
        <AlertCircle :size="21" aria-hidden="true" />
        <p>{{ store.error }}</p>
        <button type="button" @click="loadJobs">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>

      <template v-else>
        <div
          v-if="store.error"
          class="jobs-notice is-error"
          role="alert"
        >
          <AlertCircle :size="17" aria-hidden="true" />
          <p>{{ store.error }}</p>
        </div>

        <section
          v-for="section in sections"
          :key="section.key"
          class="jobs-section"
          :class="{
            'jobs-section--recommended': section.recommended
          }"
          :data-test="section.test"
          :aria-labelledby="`${section.key}-jobs-title`"
        >
          <div class="jobs-shell">
            <header class="jobs-section__heading">
              <div>
                <h2 :id="`${section.key}-jobs-title`">
                  {{ section.title }}
                </h2>
                <p>{{ section.description }}</p>
              </div>
              <span class="ark-data">
                {{ section.jobs.length }} 个岗位
              </span>
            </header>

            <div
              v-if="section.jobs.length"
              :class="section.gridClass"
            >
              <article
                v-for="job in section.jobs"
                :key="job.job_id"
                class="job-card"
                :class="{ 'job-card--recommended': section.recommended }"
                :data-test="
                  section.recommended
                    ? 'recommended-job-card'
                    : 'job-card'
                "
              >
                <RouterLink
                  class="job-card__main"
                  :to="
                    `/student/employment/jobs/${encodeURIComponent(
                      job.job_id
                    )}`
                  "
                  :aria-label="`查看${job.title}岗位详情`"
                >
                  <span class="job-card__identity">
                    <BriefcaseBusiness :size="19" aria-hidden="true" />
                    <span>{{ job.category_name }}</span>
                  </span>

                  <h3>{{ job.title }}</h3>
                  <p class="job-card__company">
                    {{ job.enterprise_name }}
                  </p>

                  <dl class="job-card__facts">
                    <div>
                      <dt>薪资</dt>
                      <dd class="ark-data">{{ job.salary }}</dd>
                    </div>
                    <div>
                      <dt>地点</dt>
                      <dd>{{ job.location }}</dd>
                    </div>
                  </dl>

                  <p class="job-card__description">
                    {{ job.description }}
                  </p>

                  <span class="job-card__action">
                    查看详情
                    <ArrowRight :size="16" aria-hidden="true" />
                  </span>
                </RouterLink>

                <button
                  class="job-card__favorite"
                  :class="{ 'is-active': isFavorite(job.job_id) }"
                  type="button"
                  data-test="favorite-toggle"
                  :data-job-id="job.job_id"
                  :aria-pressed="isFavorite(job.job_id)"
                  :disabled="
                    Boolean(favoriteActionJobId) || store.saving
                  "
                  @click="toggleFavorite(job)"
                >
                  <RefreshCw
                    v-if="favoriteActionJobId === job.job_id"
                    class="spinning"
                    :size="16"
                    aria-hidden="true"
                  />
                  <Bookmark v-else :size="16" aria-hidden="true" />
                  {{
                    isFavorite(job.job_id)
                      ? '取消收藏'
                      : '收藏岗位'
                  }}
                </button>
              </article>
            </div>

            <p v-else class="jobs-empty">
              {{ section.empty }}
            </p>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.jobs-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.jobs-main {
  min-width: 0;
  padding-bottom: 72px;
}

.jobs-shell {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding-inline: 24px;
}

.jobs-intro {
  border-bottom: 1px solid var(--ark-line-strong);
}

.jobs-intro .jobs-shell {
  padding-top: 40px;
  padding-bottom: 28px;
}

.jobs-intro h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1.08;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.jobs-intro p {
  max-width: 68ch;
  margin: 9px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.jobs-state {
  display: grid;
  min-height: 300px;
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

.jobs-state p,
.jobs-notice p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.jobs-state.is-error,
.jobs-notice.is-error {
  color: var(--ark-signal);
}

.jobs-state button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
}

.jobs-notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: min(calc(100% - 48px), 1132px);
  margin: 18px auto 0;
  padding: 11px 13px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.jobs-section {
  min-width: 0;
  padding-block: 26px 0;
}

.jobs-section--recommended {
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.jobs-section__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: end;
  min-width: 0;
  margin-bottom: 14px;
}

.jobs-section__heading > div {
  min-width: 0;
}

.jobs-section__heading h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.25;
  line-break: strict;
  text-wrap: balance;
  word-break: keep-all;
}

.jobs-section__heading p {
  margin: 5px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.jobs-section__heading > span {
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  word-break: keep-all;
}

.recommended-grid,
.job-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1px;
}

.recommended-grid,
.job-list {
  background: var(--ark-line-strong);
}

.job-card {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 236px;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.job-card__main {
  display: grid;
  min-width: 0;
  align-content: start;
  padding: 20px;
  color: var(--ark-paper);
  text-decoration: none;
}

.job-card__main:hover,
.job-card__main:focus-visible {
  background: var(--ark-surface-1);
}

.job-card__favorite {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin: 0 20px 20px;
  padding: 8px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.78rem;
  line-break: strict;
  text-align: center;
  word-break: keep-all;
}

.job-card__favorite:hover:not(:disabled),
.job-card__favorite:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.job-card__favorite.is-active {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.job-card__identity {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 7px;
  color: var(--ark-signal);
  font-size: 0.7rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.job-card h3 {
  margin: 15px 0 0;
  font-size: 1.08rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-card__company {
  margin: 5px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.job-card__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
  margin: 16px 0 0;
}

.job-card__facts > div {
  min-width: 0;
  padding-top: 9px;
  border-top: 1px solid var(--ark-line);
}

.job-card__facts dt,
.job-card__facts dd {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.job-card__facts dt {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.job-card__facts dd {
  margin: 3px 0 0;
  font-size: 0.78rem;
}

.job-card__description {
  display: -webkit-box;
  margin: 16px 0 0;
  overflow: hidden;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.job-card__action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-self: start;
  margin-top: 18px;
  color: var(--ark-signal);
  font-size: 0.76rem;
  line-break: strict;
  word-break: keep-all;
}

.jobs-empty {
  display: grid;
  min-height: 132px;
  margin: 0;
  place-items: center;
  padding: 24px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
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
  .jobs-main {
    padding-bottom: 48px;
  }

  .jobs-shell {
    padding-inline: 14px;
  }

  .jobs-intro .jobs-shell {
    padding-top: 28px;
    padding-bottom: 22px;
  }

  .jobs-intro h1 {
    font-size: 1.95rem;
  }

  .jobs-state {
    margin-inline: 14px;
  }

  .jobs-notice {
    width: calc(100% - 28px);
  }

  .jobs-section__heading {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 8px;
  }
}

@media (max-width: 360px) {
  .jobs-shell {
    padding-inline: 12px;
  }

  .job-card {
    min-height: 0;
  }

  .job-card__main {
    padding: 16px;
  }

  .job-card__favorite {
    margin: 0 16px 16px;
  }

  .job-card__facts {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
