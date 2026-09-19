<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const route = useRoute()
const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)
const recordNotice = ref('')
const notFound = computed(() => store.error === '新闻不存在')
const viewNotice = computed(() => store.viewNotice || recordNotice.value)

async function loadNewsDetail() {
  const newsId = route.params.newsId as string
  initialLoading.value = true
  loadFailed.value = false
  recordNotice.value = ''

  try {
    const opened = await store.openNews(newsId)
    loadFailed.value = !opened
    if (!opened || !store.newsDetail) {
      if (notFound.value) {
        store.newsDetail = null
      }
      return
    }

    try {
      await store.recordNewsView(newsId)
    } catch {
      recordNotice.value = '浏览量暂未记录'
    }
  } catch {
    loadFailed.value = true
    if (notFound.value) {
      store.newsDetail = null
    }
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadNewsDetail()
})
</script>

<template>
  <div class="local-resource-news-detail">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-news-detail__main">
      <header class="local-resource-news-detail__heading">
        <span class="local-resource-news-detail__code ark-data">
          06 / NEWS DETAIL
        </span>
        <h1>{{ store.newsDetail?.title ?? '新闻详情' }}</h1>

        <dl
          v-if="store.newsDetail"
          class="local-resource-news-detail__meta"
        >
          <div>
            <dt>类别</dt>
            <dd data-test="news-detail-category">
              {{ store.newsDetail.category_label }}
            </dd>
          </div>
          <div>
            <dt>时间</dt>
            <dd>
              <time
                data-test="news-published-at"
                :datetime="store.newsDetail.published_at"
              >
                {{ store.newsDetail.published_at }}
              </time>
            </dd>
          </div>
        </dl>
      </header>

      <article
        v-if="store.newsDetail && !loadFailed && !notFound"
        class="local-resource-news-detail__content"
      >
        <p data-test="news-content">{{ store.newsDetail.content }}</p>
        <p
          v-if="viewNotice"
          class="local-resource-news-detail__notice"
          data-test="news-view-notice"
          role="status"
          aria-live="polite"
        >
          {{ viewNotice }}
        </p>
      </article>

      <div
        v-else-if="initialLoading"
        class="local-resource-news-detail__status"
        data-test="news-detail-loading"
        role="status"
      >
        正在加载新闻详情
      </div>

      <p
        v-else-if="notFound"
        class="local-resource-news-detail__status"
        data-test="news-not-found"
        role="alert"
      >
        新闻不存在
      </p>

      <p
        v-else
        class="local-resource-news-detail__status"
        data-test="news-detail-unavailable"
        role="alert"
      >
        新闻数据暂不可用
      </p>
    </main>
  </div>
</template>

<style scoped>
.local-resource-news-detail {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-news-detail__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-news-detail__heading {
  padding-bottom: 28px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-news-detail__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-news-detail__heading h1 {
  max-width: 32ch;
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.08;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: keep-all;
}

.local-resource-news-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 30px;
  margin: 18px 0 0;
}

.local-resource-news-detail__meta div {
  min-width: 0;
}

.local-resource-news-detail__meta dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-news-detail__meta dd {
  min-width: 0;
  margin: 2px 0 0;
  color: var(--ark-paper);
  font-size: 0.9rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-news-detail__content {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-news-detail__content > p:first-child {
  max-width: 78ch;
  margin: 0;
  padding: 24px 0 28px;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: pre-wrap;
  word-break: keep-all;
}

.local-resource-news-detail__notice {
  margin: 0;
  padding: 11px 0 13px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-state);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-news-detail__status {
  display: flex;
  min-height: 260px;
  align-items: center;
  justify-content: center;
  margin: 22px 0 0;
  border-top: 1px solid var(--ark-line-strong);
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: keep-all;
}

@media (max-width: 640px) {
  .local-resource-news-detail__main {
    padding: 28px 14px 48px;
  }

  .local-resource-news-detail__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-news-detail__meta {
    display: grid;
    gap: 10px;
  }

  .local-resource-news-detail__content > p:first-child {
    padding-block: 20px 24px;
  }
}
</style>
