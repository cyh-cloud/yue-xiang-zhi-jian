<script setup lang="ts">
import {
  CheckCircle2,
  Eye,
  Filter,
  Newspaper,
  RefreshCw,
  Send,
  ShieldAlert,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type { GovernmentNews } from '@/api/types'
import GovernmentConsoleNav from '@/components/GovernmentConsoleNav.vue'
import { useGovernmentConsoleStore } from '@/stores/governmentConsole'

type NewsCategoryCode = GovernmentNews['category_code']

const newsCategories = [
  ['news', '新闻'],
  ['disaster_warning', '灾害预警'],
  ['policy_update', '政策更新']
] as const satisfies readonly (readonly [NewsCategoryCode, string])[]

const store = useGovernmentConsoleStore()
const title = ref('')
const content = ref('')
const categoryCode = ref<NewsCategoryCode>('news')
const categoryFilter = ref<'all' | NewsCategoryCode>('all')
const deleteCandidateId = ref<string | null>(null)
const pendingRequestId = ref<string | null>(null)
const actionMessage = ref('')
const initialLoading = ref(true)

const filteredNews = computed(() =>
  store.news.filter(news => {
    return (
      categoryFilter.value === 'all' ||
      news.category_code === categoryFilter.value
    )
  })
)

function categoryLabel(category: NewsCategoryCode): string {
  return (
    newsCategories.find(([code]) => code === category)?.[1] ?? category
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

async function loadNewsList() {
  initialLoading.value = true
  try {
    await store.loadNews()
  } finally {
    initialLoading.value = false
  }
}

function publicationRequestId(): string {
  if (!pendingRequestId.value) {
    pendingRequestId.value = globalThis.crypto.randomUUID()
  }
  return pendingRequestId.value
}

async function submitNews() {
  if (!title.value.trim() || !content.value.trim()) {
    return
  }

  actionMessage.value = ''
  const published = await store.publishNews({
    request_id: publicationRequestId(),
    title: title.value.trim(),
    content: content.value.trim(),
    category_code: categoryCode.value
  })

  if (!published) {
    return
  }

  pendingRequestId.value = null
  title.value = ''
  content.value = ''
  categoryCode.value = 'news'
  actionMessage.value = '新闻已发布'
}

function requestDelete(news: GovernmentNews) {
  actionMessage.value = ''
  deleteCandidateId.value = news.id
}

function cancelDelete() {
  deleteCandidateId.value = null
}

async function confirmDelete(news: GovernmentNews) {
  actionMessage.value = ''
  const deleted = await store.deleteNews(news.id, news.version)
  deleteCandidateId.value = null
  if (deleted) {
    actionMessage.value = '新闻已删除'
  }
}

onMounted(() => {
  void loadNewsList()
})
</script>

<template>
  <div class="government-news-page" data-test="government-news-page">
    <GovernmentConsoleNav />

    <main
      class="government-news"
      data-ark-theme="ark"
      data-ark-depth="maximal"
    >
      <header class="news-hero">
        <div class="news-hero__identity">
          <Newspaper :size="25" aria-hidden="true" />
          <div>
            <span class="ark-data">NEWS REGISTRY</span>
            <h1>新闻管理</h1>
            <p>
              发布三类新闻并维护已发布记录。
              新闻发布后立即对学员可见，删除后不可恢复。
            </p>
          </div>
        </div>
      </header>

      <section class="news-compose" aria-labelledby="news-compose-title">
        <header class="section-heading">
          <div>
            <span class="ark-data">PUBLISH NEWS</span>
            <h2 id="news-compose-title">发布新闻</h2>
          </div>
          <span class="ark-data">三类</span>
        </header>

        <form
          class="news-form"
          data-test="news-form"
          @submit.prevent="submitNews"
        >
          <div class="news-compose__grid">
            <label class="news-field">
              <span>新闻标题</span>
              <input
                v-model="title"
                data-test="news-title"
                name="title"
                type="text"
                maxlength="120"
                autocomplete="off"
                required
              />
            </label>

            <label class="news-field">
              <span>新闻分类</span>
              <select
                v-model="categoryCode"
                data-test="news-category"
                name="category_code"
                required
              >
                <option
                  v-for="[code, label] in newsCategories"
                  :key="code"
                  :value="code"
                >
                  {{ label }}
                </option>
              </select>
            </label>

            <label class="news-field news-field--wide">
              <span>新闻正文</span>
              <textarea
                v-model="content"
                data-test="news-content"
                name="content"
                rows="6"
                required
              />
            </label>
          </div>

          <div class="news-compose__actions">
            <p>发布即对学员可见，分类由发布者手动选择。</p>
            <button
              class="news-submit"
              type="submit"
              :disabled="
                store.loading ||
                !title.trim() ||
                !content.trim()
              "
            >
              <Send :size="17" aria-hidden="true" />
              {{ store.loading ? '发布中' : '发布新闻' }}
            </button>
          </div>
        </form>
      </section>

      <div
        v-if="actionMessage"
        class="news-message"
        data-test="news-message"
        role="status"
      >
        <CheckCircle2 :size="18" aria-hidden="true" />
        <span>{{ actionMessage }}</span>
      </div>

      <div
        v-if="store.error"
        class="news-error"
        data-test="news-error"
        role="alert"
      >
        <ShieldAlert :size="18" aria-hidden="true" />
        <span>{{ store.error }}</span>
        <button type="button" @click="loadNewsList">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>

      <section class="news-registry" aria-labelledby="news-registry-title">
        <header class="section-heading news-registry__heading">
          <div>
            <span class="ark-data">NEWS REGISTRY</span>
            <h2 id="news-registry-title">新闻目录</h2>
          </div>
          <span class="ark-data">{{ filteredNews.length }} 条</span>
        </header>

        <div class="news-registry__filters">
          <label class="news-field">
            <span>
              <Filter :size="15" aria-hidden="true" />
              分类筛选
            </span>
            <select
              v-model="categoryFilter"
              data-test="news-category-filter"
            >
              <option value="all">全部分类</option>
              <option
                v-for="[code, label] in newsCategories"
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
            store.news.length === 0
          "
          class="news-status"
          data-test="news-loading"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          正在加载新闻
        </div>

        <p
          v-else-if="filteredNews.length === 0"
          class="news-empty"
          data-test="news-empty"
        >
          暂无新闻
        </p>

        <div v-else class="news-table-wrap">
          <table class="news-table">
            <colgroup>
              <col class="news-table__col-title" />
              <col class="news-table__col-category" />
              <col class="news-table__col-published" />
              <col class="news-table__col-views" />
              <col class="news-table__col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">新闻标题</th>
                <th scope="col">分类</th>
                <th scope="col">发布时间</th>
                <th scope="col">浏览量</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="news in filteredNews"
                :key="news.id"
                data-test="news-row"
                :data-news-id="news.id"
              >
                <td data-label="新闻标题">
                  <strong class="news-table__title">
                    {{ news.title }}
                  </strong>
                </td>
                <td data-label="分类">
                  {{ categoryLabel(news.category_code) }}
                </td>
                <td data-label="发布时间">
                  <time
                    class="ark-data news-published-at"
                    :datetime="news.published_at"
                  >
                    {{ formatPublishedAt(news.published_at) }}
                  </time>
                </td>
                <td data-label="浏览量">
                  <span class="news-views ark-data">
                    <Eye :size="15" aria-hidden="true" />
                    {{ news.view_count }}
                  </span>
                </td>
                <td data-label="操作">
                  <div class="news-actions">
                    <button
                      class="news-delete-trigger"
                      type="button"
                      data-test="delete-news"
                      :aria-label="`删除新闻：${news.title}`"
                      :title="`删除新闻：${news.title}`"
                      :disabled="store.loading"
                      @click="requestDelete(news)"
                    >
                      <Trash2 :size="16" aria-hidden="true" />
                      <span>删除</span>
                    </button>
                  </div>

                  <div
                    v-if="deleteCandidateId === news.id"
                    class="news-delete-confirmation"
                    data-test="news-delete-confirmation"
                  >
                    <p>
                      确认彻底删除「{{ news.title }}」？删除后不可恢复。
                    </p>
                    <div>
                      <button
                        type="button"
                        data-test="confirm-delete-news"
                        :disabled="store.loading"
                        @click="confirmDelete(news)"
                      >
                        <Trash2 :size="15" aria-hidden="true" />
                        确认删除
                      </button>
                      <button
                        type="button"
                        data-test="cancel-delete-news"
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
.government-news-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.government-news {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
  color: var(--ark-paper);
}

.news-hero {
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.news-hero__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.news-hero__identity > svg {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--ark-signal);
}

.news-hero__identity > div {
  min-width: 0;
}

.news-hero__identity span,
.section-heading span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.news-hero__identity h1 {
  margin: 4px 0 0;
  font-size: 2.55rem;
  line-height: 1;
  text-wrap: balance;
}

.news-hero__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-compose,
.news-registry {
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

.news-form {
  min-width: 0;
  padding: 18px;
}

.news-compose__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(190px, 0.75fr);
  gap: 14px;
  min-width: 0;
}

.news-field {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.news-field > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  word-break: keep-all;
}

.news-field input,
.news-field select,
.news-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.news-field textarea {
  min-height: 138px;
  resize: vertical;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.news-field input::placeholder,
.news-field textarea::placeholder {
  color: var(--ark-muted);
}

.news-field input:hover,
.news-field select:hover,
.news-field textarea:hover {
  border-color: var(--ark-signal);
}

.news-field--wide {
  grid-column: 1 / -1;
}

.news-compose__actions {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 16px;
}

.news-compose__actions p {
  max-width: 65ch;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-submit,
.news-error button,
.news-actions button,
.news-delete-confirmation button {
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

.news-submit {
  flex: 0 0 auto;
  min-height: 44px;
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.news-submit:hover:not(:disabled),
.news-error button:hover:not(:disabled),
.news-actions button:hover:not(:disabled),
.news-delete-confirmation button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.news-message,
.news-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.news-message {
  color: var(--ark-state);
}

.news-message svg,
.news-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.news-message span,
.news-error > span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-error {
  color: var(--ark-paper);
}

.news-error button {
  flex: 0 0 auto;
  margin-left: auto;
}

.news-registry__filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  gap: 14px;
  min-width: 0;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.news-status,
.news-empty {
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

.news-table-wrap {
  min-width: 0;
  overflow-x: clip;
}

.news-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
}

.news-table__col-title {
  width: 30%;
}

.news-table__col-category {
  width: 14%;
}

.news-table__col-published {
  width: 21%;
}

.news-table__col-views {
  width: 13%;
}

.news-table__col-actions {
  width: 22%;
}

.news-table th,
.news-table td {
  min-width: 0;
  padding: 14px 12px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.news-table th {
  color: var(--ark-muted);
  font-size: 0.72rem;
  font-weight: 500;
  line-break: strict;
  white-space: nowrap;
  word-break: keep-all;
}

.news-table td {
  color: var(--ark-paper);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-table tbody tr:last-child td {
  border-bottom: 0;
}

.news-table__title {
  min-width: 0;
  line-height: 1.35;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-published-at {
  color: var(--ark-muted);
  font-size: 0.7rem;
  white-space: nowrap;
}

.news-views {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.news-views svg {
  color: var(--ark-muted);
}

.news-actions {
  display: flex;
  min-width: 0;
}

.news-actions button {
  flex: 1 1 88px;
}

.news-delete-trigger {
  border-color: var(--ark-line-strong);
}

.news-delete-confirmation {
  margin-top: 10px;
  padding: 11px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.news-delete-confirmation p {
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.news-delete-confirmation > div {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 9px;
}

.news-delete-confirmation button {
  flex: 1 1 100px;
}

.news-delete-confirmation button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.government-news :is(button, a, input, select, textarea):focus-visible {
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
  .government-news {
    padding: 28px 14px 48px;
  }

  .news-hero__identity {
    padding: 20px 16px;
  }

  .news-hero__identity h1 {
    font-size: 2.15rem;
  }

  .news-compose__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .news-compose__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .news-submit {
    width: 100%;
  }

  .news-error {
    align-items: flex-start;
    flex-direction: column;
  }

  .news-error button {
    width: 100%;
    margin-left: 0;
  }

  .news-table-wrap {
    overflow-x: visible;
  }

  .news-table {
    display: block;
    table-layout: auto;
  }

  .news-table colgroup,
  .news-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .news-table tbody {
    display: grid;
    min-width: 0;
    gap: 1px;
    background: var(--ark-line);
  }

  .news-table tr {
    display: grid;
    min-width: 0;
    padding: 12px 14px;
    background: var(--ark-surface-0);
  }

  .news-table td {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .news-table td::before {
    color: var(--ark-muted);
    content: attr(data-label);
    font-size: 0.7rem;
    line-break: strict;
    word-break: keep-all;
  }

  .news-table td:last-child {
    border-bottom: 0;
  }

  .news-table__title {
    text-align: right;
  }

  .news-actions {
    justify-content: flex-end;
  }

  .news-delete-confirmation {
    grid-column: 1 / -1;
    text-align: left;
  }
}

@media (max-width: 420px) {
  .news-table td {
    grid-template-columns: minmax(0, 1fr);
  }

  .news-table__title {
    text-align: left;
  }

  .news-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    width: 100%;
  }

  .news-actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
