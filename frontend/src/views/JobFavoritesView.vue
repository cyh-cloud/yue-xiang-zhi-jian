<script setup lang="ts">
import {
  AlertCircle,
  ArrowRight,
  Ban,
  Bookmark,
  RefreshCw,
  Trash2
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { JobFavorite } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useJobMatchingStore } from '@/stores/jobMatching'

const auth = useAuthStore()
const router = useRouter()
const store = useJobMatchingStore()
const removingJobId = ref('')

const showInitialLoading = computed(
  () => store.loading && store.favorites.length === 0
)
const showInitialError = computed(
  () =>
    !store.loading &&
    store.favorites.length === 0 &&
    store.error.length > 0
)

const favoritedAtFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23'
})

function displayTitle(favorite: JobFavorite): string {
  return favorite.closed
    ? favorite.title_snapshot || favorite.title
    : favorite.title || favorite.title_snapshot
}

function displayEnterpriseName(favorite: JobFavorite): string {
  return favorite.closed
    ? favorite.enterprise_name_snapshot || favorite.enterprise_name
    : favorite.enterprise_name || favorite.enterprise_name_snapshot
}

function formatFavoritedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  const values = Object.fromEntries(
    favoritedAtFormatter
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )

  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`
}

function jobPath(jobId: string): string {
  return `/student/employment/jobs/${encodeURIComponent(jobId)}`
}

async function loadFavorites() {
  await store.loadFavorites()
}

async function removeFavorite(jobId: string) {
  if (removingJobId.value) {
    return
  }

  removingJobId.value = jobId
  await store.removeFavorite(jobId)
  removingJobId.value = ''
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadFavorites()
})
</script>

<template>
  <div class="favorites-page">
    <AppHeader
      source="live"
      :loading="store.loading || Boolean(removingJobId)"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <JobMatchingNav />

    <main class="favorites-main">
      <header class="favorites-heading">
        <h1>岗位收藏</h1>
        <p>集中查看仍在招聘的岗位和已关闭岗位的最后展示信息。</p>
      </header>

      <section
        v-if="showInitialLoading"
        class="favorites-state"
        data-test="favorites-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="21" aria-hidden="true" />
        <p>正在加载收藏岗位</p>
      </section>

      <section
        v-else-if="showInitialError"
        class="favorites-state is-error"
        data-test="favorites-error"
        role="alert"
      >
        <AlertCircle :size="21" aria-hidden="true" />
        <p>{{ store.error }}</p>
        <button type="button" @click="loadFavorites">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>

      <template v-else>
        <div
          v-if="store.error"
          class="favorites-notice is-error"
          role="alert"
        >
          <AlertCircle :size="17" aria-hidden="true" />
          <p>{{ store.error }}</p>
          <button type="button" @click="loadFavorites">
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </div>

        <section
          class="favorites-content"
          aria-labelledby="favorites-list-title"
        >
          <h2 id="favorites-list-title" class="ark-sr-only">
            收藏岗位列表
          </h2>

          <div
            v-if="store.favorites.length === 0"
            class="favorites-empty"
            data-test="favorites-empty"
          >
            <Bookmark :size="23" aria-hidden="true" />
            <p>暂无收藏岗位</p>
          </div>

          <ul v-else class="favorite-list">
            <li
              v-for="favorite in store.favorites"
              :key="favorite.job_id"
              class="favorite-card"
              :class="{ 'is-closed': favorite.closed }"
              :data-test="
                favorite.closed ? 'favorite-closed' : 'favorite-available'
              "
            >
              <div class="favorite-card__heading">
                <span class="favorite-card__icon" aria-hidden="true">
                  <Bookmark :size="19" />
                </span>

                <span
                  v-if="favorite.closed"
                  class="favorite-card__closed"
                  data-test="favorite-closed-label"
                >
                  岗位已关闭
                </span>
                <span v-else class="favorite-card__available">
                  当前可查看
                </span>
              </div>

              <h2>{{ displayTitle(favorite) }}</h2>
              <p class="favorite-card__company">
                {{ displayEnterpriseName(favorite) }}
              </p>

              <dl class="favorite-card__facts">
                <div>
                  <dt>薪资</dt>
                  <dd class="ark-data">{{ favorite.salary }}</dd>
                </div>
                <div>
                  <dt>地点</dt>
                  <dd>{{ favorite.location }}</dd>
                </div>
                <div>
                  <dt>收藏时间</dt>
                  <dd>
                    <time :datetime="favorite.favorited_at">
                      {{ formatFavoritedAt(favorite.favorited_at) }}
                    </time>
                  </dd>
                </div>
              </dl>

              <p class="favorite-card__description">
                {{ favorite.description }}
              </p>

              <div class="favorite-card__actions">
                <RouterLink
                  v-if="!favorite.closed"
                  class="favorite-card__apply"
                  data-test="apply-favorite"
                  :to="jobPath(favorite.job_id)"
                >
                  <ArrowRight :size="16" aria-hidden="true" />
                  查看岗位
                </RouterLink>
                <button
                  v-else
                  class="favorite-card__apply is-disabled"
                  data-test="apply-favorite"
                  type="button"
                  disabled
                >
                  <Ban :size="16" aria-hidden="true" />
                  不可投递
                </button>

                <button
                  class="favorite-card__remove"
                  data-test="remove-favorite"
                  type="button"
                  :disabled="removingJobId === favorite.job_id"
                  @click="removeFavorite(favorite.job_id)"
                >
                  <Trash2 :size="16" aria-hidden="true" />
                  移除收藏
                </button>
              </div>
            </li>
          </ul>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.favorites-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.favorites-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  overflow-x: clip;
}

.favorites-heading {
  min-width: 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.favorites-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.04;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.favorites-heading p {
  max-width: 66ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.favorites-state {
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

.favorites-state p,
.favorites-notice p,
.favorites-empty p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.favorites-state.is-error {
  color: var(--ark-signal);
}

.favorites-state button,
.favorites-notice button {
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

.favorites-state button:hover,
.favorites-state button:focus-visible,
.favorites-notice button:hover,
.favorites-notice button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.favorites-notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.favorites-notice.is-error {
  color: var(--ark-signal);
}

.favorites-content {
  min-width: 0;
  margin-top: 18px;
}

.favorites-empty {
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

.favorite-list {
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(min(100%, 310px), 1fr)
  );
  gap: 12px;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.favorite-card {
  display: grid;
  min-width: 0;
  min-height: 350px;
  align-content: start;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.favorite-card.is-closed {
  background: var(--ark-surface-1);
}

.favorite-card__heading {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.favorite-card__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
}

.favorite-card__available,
.favorite-card__closed {
  display: inline-flex;
  min-width: 0;
  min-height: 28px;
  align-items: center;
  padding: 4px 8px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  font-size: 0.7rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.favorite-card__closed {
  color: var(--ark-state);
}

.favorite-card h2 {
  margin: 16px 0 0;
  font-size: 1.08rem;
  line-height: 1.4;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.favorite-card__company {
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.favorite-card__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  min-width: 0;
  margin: 17px 0 0;
}

.favorite-card__facts > div {
  min-width: 0;
  padding-top: 9px;
  border-top: 1px solid var(--ark-line);
}

.favorite-card__facts > div:last-child {
  grid-column: 1 / -1;
}

.favorite-card__facts dt,
.favorite-card__facts dd {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.favorite-card__facts dt {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.favorite-card__facts dd {
  margin: 3px 0 0;
  font-size: 0.8rem;
}

.favorite-card__facts time {
  font-variant-numeric: tabular-nums;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.favorite-card__description {
  display: -webkit-box;
  margin: 16px 0 0;
  overflow: hidden;
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.favorite-card__actions {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 9px;
  align-self: end;
  margin-top: 20px;
}

.favorite-card__apply,
.favorite-card__remove {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  flex: 1 1 132px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-decoration: none;
  text-wrap: pretty;
  word-break: normal;
}

.favorite-card__apply {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.favorite-card__apply:hover,
.favorite-card__apply:focus-visible,
.favorite-card__remove:hover,
.favorite-card__remove:focus-visible {
  background: var(--ark-surface-1);
}

.favorite-card__apply.is-disabled {
  border-color: var(--ark-line-strong);
  color: var(--ark-muted);
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
  .favorites-main {
    padding: 28px 14px 48px;
  }

  .favorites-heading h1 {
    font-size: 2.25rem;
  }

  .favorites-notice {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .favorites-notice button {
    grid-column: 1 / -1;
    width: 100%;
  }
}

@media (max-width: 360px) {
  .favorites-main {
    padding-inline: 12px;
  }

  .favorite-card {
    padding: 16px;
  }

  .favorite-card__facts {
    grid-template-columns: minmax(0, 1fr);
  }

  .favorite-card__facts > div:last-child {
    grid-column: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
