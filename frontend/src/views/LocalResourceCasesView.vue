<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)

async function loadCaseList() {
  initialLoading.value = true
  try {
    loadFailed.value = !(await store.loadCases())
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadCaseList()
})
</script>

<template>
  <div class="local-resource-cases">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-cases__main">
      <header class="local-resource-cases__heading">
        <span class="local-resource-cases__code ark-data">
          06 / SUCCESS CASES
        </span>
        <h1>成功案例</h1>
        <p>阅读本地创业者的真实经历，了解从起步到成长的关键选择。</p>
      </header>

      <section
        class="local-resource-cases__registry"
        aria-labelledby="local-resource-cases-title"
      >
        <header class="local-resource-cases__section-head">
          <span class="ark-data">CASE REGISTRY</span>
          <h2 id="local-resource-cases-title">案例目录</h2>
        </header>

        <p
          v-if="loadFailed"
          class="local-resource-cases__status"
          data-test="cases-unavailable"
          role="alert"
        >
          案例数据暂不可用
        </p>

        <ul
          v-else-if="store.cases.length > 0"
          class="local-resource-cases__list"
        >
          <li v-for="item in store.cases" :key="item.id">
            <RouterLink
              class="local-resource-cases__link"
              :to="`/student/local-resources/cases/${item.id}`"
              data-test="case-link"
            >
              <span class="local-resource-cases__copy">
                <span
                  v-if="item.is_demo"
                  class="local-resource-cases__demo"
                >
                  演示数据
                </span>
                <strong>{{ item.title }}</strong>
                <span>{{ item.summary }}</span>
              </span>
              <ArrowRight :size="20" aria-hidden="true" />
            </RouterLink>
          </li>
        </ul>

        <p
          v-else
          class="local-resource-cases__status"
          data-test="cases-empty"
        >
          暂无成功案例
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.local-resource-cases {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-cases__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-cases__heading {
  padding-bottom: 26px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-cases__code,
.local-resource-cases__section-head > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-cases__heading h1 {
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.05;
  text-wrap: balance;
}

.local-resource-cases__heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-cases__registry {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-cases__section-head {
  display: grid;
  gap: 3px;
  padding: 18px 0 12px;
}

.local-resource-cases__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.local-resource-cases__list {
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--ark-line-strong);
  list-style: none;
}

.local-resource-cases__list li {
  border-bottom: 1px solid var(--ark-line);
}

.local-resource-cases__link {
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

.local-resource-cases__link:hover,
.local-resource-cases__link:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.local-resource-cases__link > svg {
  color: var(--ark-muted);
}

.local-resource-cases__copy {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.local-resource-cases__copy strong {
  min-width: 0;
  font-size: 1.14rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-cases__copy > span:last-child {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.88rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-cases__demo {
  width: fit-content;
  padding: 2px 7px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-size: 0.72rem;
  font-weight: 700;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-cases__status {
  display: flex;
  min-height: 220px;
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

@media (max-width: 640px) {
  .local-resource-cases__main {
    padding: 28px 14px 48px;
  }

  .local-resource-cases__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-cases__link {
    gap: 12px;
    min-height: 112px;
    padding: 18px 4px;
  }
}
</style>
