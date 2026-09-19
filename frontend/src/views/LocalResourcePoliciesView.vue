<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type {
  PolicyCategoryCode,
  PolicyCategorySubscription
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)
const selectedCategory = ref<PolicyCategoryCode | null>(null)

async function loadPolicyLibrary() {
  initialLoading.value = true
  try {
    const [subscriptionsLoaded, policiesLoaded] = await Promise.all([
      store.loadSubscriptions(),
      store.loadPolicies()
    ])
    loadFailed.value = !subscriptionsLoaded || !policiesLoaded
  } finally {
    initialLoading.value = false
  }
}

async function selectCategory(category: PolicyCategoryCode) {
  selectedCategory.value = category
  loadFailed.value = !(await store.loadPolicies(category))
}

async function toggleSubscription(category: PolicyCategorySubscription) {
  if (category.subscribed) {
    await store.unsubscribePolicyCategory(category.code)
  } else {
    await store.subscribePolicyCategory(category.code)
  }
}

onMounted(() => {
  void loadPolicyLibrary()
})
</script>

<template>
  <div class="local-resource-policies">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-policies__main">
      <header class="local-resource-policies__heading">
        <span class="local-resource-policies__code ark-data">
          06 / POLICY DESK
        </span>
        <h1>本地政策</h1>
        <p>按类别查看已上架政策，并分别管理自己关注的政策订阅。</p>
      </header>

      <section
        class="local-resource-policies__subscriptions"
        aria-labelledby="policy-subscriptions-title"
      >
        <header class="local-resource-policies__section-head">
          <span class="ark-data">SUBSCRIPTIONS</span>
          <h2 id="policy-subscriptions-title">政策订阅</h2>
        </header>

        <p
          v-if="loadFailed && store.subscriptions.categories.length === 0"
          class="local-resource-policies__status"
          data-test="policies-unavailable"
          role="alert"
        >
          政策数据暂不可用
        </p>

        <ul
          v-else
          class="local-resource-policies__category-list"
          aria-label="政策类别"
        >
          <li
            v-for="category in store.subscriptions.categories"
            :key="category.code"
            class="local-resource-policies__category"
            :class="{
              'is-selected': selectedCategory === category.code,
              'is-subscribed': category.subscribed
            }"
            :data-category="category.code"
          >
            <button
              class="local-resource-policies__category-select"
              type="button"
              data-test="policy-category"
              :aria-pressed="selectedCategory === category.code"
              @click="selectCategory(category.code)"
            >
              <span>{{ category.label }}</span>
              <span
                v-if="category.recommended"
                class="local-resource-policies__recommended"
                data-test="policy-recommended"
              >
                推荐
              </span>
            </button>
            <button
              class="local-resource-policies__subscription-toggle"
              type="button"
              data-test="policy-subscription-toggle"
              :aria-pressed="category.subscribed"
              @click="toggleSubscription(category)"
            >
              <span data-test="policy-subscription-state">
                {{ category.subscribed ? '已订阅' : '未订阅' }}
              </span>
              <span>
                {{ category.subscribed ? '取消订阅' : '订阅' }}
              </span>
            </button>
          </li>
        </ul>
      </section>

      <section
        class="local-resource-policies__registry"
        aria-labelledby="local-resource-policies-title"
      >
        <header class="local-resource-policies__section-head">
          <span class="ark-data">POLICY REGISTRY</span>
          <h2 id="local-resource-policies-title">政策目录</h2>
        </header>

        <ul
          v-if="store.policies.length > 0"
          class="local-resource-policies__list"
        >
          <li v-for="policy in store.policies" :key="policy.id">
            <RouterLink
              class="local-resource-policies__link"
              :to="`/student/local-resources/policies/${policy.id}`"
              data-test="policy-link"
            >
              <span class="local-resource-policies__copy">
                <strong>{{ policy.title }}</strong>
                <span>{{ policy.category_label }}</span>
                <time :datetime="policy.published_at">
                  {{ policy.published_at }}
                </time>
              </span>
              <ArrowRight :size="20" aria-hidden="true" />
            </RouterLink>
          </li>
        </ul>

        <p
          v-else-if="initialLoading || store.loading"
          class="local-resource-policies__status"
          data-test="policies-loading"
          role="status"
        >
          正在加载政策
        </p>

        <p
          v-else-if="loadFailed"
          class="local-resource-policies__status"
          data-test="policies-unavailable"
          role="alert"
        >
          政策数据暂不可用
        </p>

        <p
          v-else
          class="local-resource-policies__status"
          data-test="policies-empty"
        >
          暂无政策
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.local-resource-policies {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-policies__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-policies__heading {
  padding-bottom: 26px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-policies__code,
.local-resource-policies__section-head > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-policies__heading h1 {
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.05;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: keep-all;
}

.local-resource-policies__heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-policies__subscriptions,
.local-resource-policies__registry {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-policies__section-head {
  display: grid;
  gap: 3px;
  padding: 18px 0 12px;
}

.local-resource-policies__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.local-resource-policies__category-list,
.local-resource-policies__list {
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--ark-line-strong);
  list-style: none;
}

.local-resource-policies__category-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  border-bottom: 1px solid var(--ark-line);
}

.local-resource-policies__category {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
  padding: 14px 12px;
  border-bottom: 1px solid var(--ark-line);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-policies__category.is-selected {
  background: var(--ark-surface-1);
}

.local-resource-policies__category-select {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ark-paper);
  font-weight: 700;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: left;
  word-break: keep-all;
}

.local-resource-policies__recommended {
  flex: none;
  padding: 1px 6px;
  border: 1px solid var(--ark-state);
  color: var(--ark-state);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-policies__subscription-toggle {
  display: grid;
  gap: 1px;
  min-width: 82px;
  padding: 7px 9px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.76rem;
  line-height: 1.3;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  word-break: keep-all;
}

.local-resource-policies__subscription-toggle > span:first-child {
  color: var(--ark-muted);
}

.local-resource-policies__category.is-subscribed
  .local-resource-policies__subscription-toggle {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.local-resource-policies__list li {
  border-bottom: 1px solid var(--ark-line);
}

.local-resource-policies__link {
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

.local-resource-policies__link:hover,
.local-resource-policies__link:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.local-resource-policies__link > svg {
  color: var(--ark-muted);
}

.local-resource-policies__copy {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.local-resource-policies__copy strong {
  min-width: 0;
  font-size: 1.14rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-policies__copy span,
.local-resource-policies__copy time {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-policies__status {
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
  .local-resource-policies__main {
    padding: 28px 14px 48px;
  }

  .local-resource-policies__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-policies__category-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .local-resource-policies__link {
    gap: 12px;
    min-height: 112px;
    padding: 18px 4px;
  }
}
</style>
