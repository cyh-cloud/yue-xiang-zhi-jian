<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { NewsCategoryCode } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const categories = [
  { code: 'news', label: '新闻' },
  { code: 'disaster_warning', label: '灾害预警' },
  { code: 'policy_update', label: '政策更新' }
] as const

const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)
const selectedCategory = ref<NewsCategoryCode | null>(null)

async function loadNewsList() {
  initialLoading.value = true
  try {
    loadFailed.value = !(await store.loadNews())
  } finally {
    initialLoading.value = false
  }
}

async function selectCategory(category: NewsCategoryCode) {
  selectedCategory.value = category
  loadFailed.value = !(await store.loadNews(category))
}

onMounted(() => {
  void loadNewsList()
})
</script>

<template>
  <div class="local-resource-news">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-news__main">
      <header class="local-resource-news__heading">
        <span class="local-resource-news__code ark-data">
          06 / NEWS DESK
        </span>
        <h1>新闻</h1>
        <p>按新闻、灾害预警和政策更新分类，查看当前公开内容。</p>
      </header>

      <section
        class="local-resource-news__registry"
        aria-labelledby="local-resource-news-title"
      >
        <header class="local-resource-news__section-head">
          <span class="ark-data">NEWS REGISTRY</span>
          <h2 id="local-resource-news-title">新闻目录</h2>
        </header>

        <div
          class="local-resource-news__categories"
          aria-label="新闻类别"
        >
          <button
            v-for="category in categories"
            :key="category.code"
            class="local-resource-news__category"
            :class="{
              'is-active': selectedCategory === category.code
            }"
            type="button"
            data-test="news-category"
            :aria-pressed="selectedCategory === category.code"
            @click="selectCategory(category.code)"
          >
            {{ category.label }}
          </button>
        </div>

        <ul
          v-if="store.news.length > 0"
          class="local-resource-news__list"
        >
          <li v-for="item in store.news" :key="item.id">
            <RouterLink
              class="local-resource-news__link"
              :to="`/student/local-resources/news/${item.id}`"
              data-test="news-link"
            >
              <span class="local-resource-news__copy">
                <strong>{{ item.title }}</strong>
                <span>{{ item.category_label }}</span>
                <time :datetime="item.published_at">
                  {{ item.published_at }}
                </time>
              </span>
              <ArrowRight :size="20" aria-hidden="true" />
            </RouterLink>
          </li>
        </ul>

        <p
          v-else-if="initialLoading || store.loading"
          class="local-resource-news__status"
          data-test="news-loading"
          role="status"
        >
          正在加载新闻
        </p>

        <p
          v-else-if="loadFailed"
          class="local-resource-news__status"
          data-test="news-unavailable"
          role="alert"
        >
          新闻数据暂不可用
        </p>

        <p
          v-else
          class="local-resource-news__status"
          data-test="news-empty"
        >
          暂无新闻
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.local-resource-news {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-news__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-news__heading {
  padding-bottom: 26px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-news__code,
.local-resource-news__section-head > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-news__heading h1 {
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.05;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: keep-all;
}

.local-resource-news__heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-news__registry {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-news__section-head {
  display: grid;
  gap: 3px;
  padding: 18px 0 12px;
}

.local-resource-news__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.local-resource-news__categories {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-block: 1px solid var(--ark-line-strong);
}

.local-resource-news__category {
  min-width: 0;
  min-height: 46px;
  padding: 10px 8px;
  border: 0;
  border-right: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-muted);
  font: inherit;
  font-weight: 700;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
  cursor: pointer;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.local-resource-news__category:last-child {
  border-right: 0;
}

.local-resource-news__category:hover,
.local-resource-news__category:focus-visible,
.local-resource-news__category.is-active {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.local-resource-news__list {
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--ark-line-strong);
  list-style: none;
}

.local-resource-news__list li {
  border-bottom: 1px solid var(--ark-line);
}

.local-resource-news__link {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
  min-width: 0;
  min-height: 124px;
  padding: 20px 14px;
  color: var(--ark-paper);
  text-decoration: none;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.local-resource-news__link:hover,
.local-resource-news__link:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.local-resource-news__link > svg {
  color: var(--ark-muted);
}

.local-resource-news__copy {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.local-resource-news__copy strong {
  min-width: 0;
  font-size: 1.14rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-news__copy span,
.local-resource-news__copy time {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-news__status {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  margin: 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: keep-all;
}

@media (max-width: 640px) {
  .local-resource-news__main {
    padding: 28px 14px 48px;
  }

  .local-resource-news__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-news__category {
    padding-inline: 4px;
    font-size: 0.82rem;
  }

  .local-resource-news__link {
    gap: 12px;
    min-height: 112px;
    padding: 18px 4px;
  }
}
</style>
