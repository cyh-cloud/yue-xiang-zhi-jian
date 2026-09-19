<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import { useLocalResourcesStore } from '@/stores/localResources'

const route = useRoute()
const store = useLocalResourcesStore()
const initialLoading = ref(true)
const loadFailed = ref(false)

async function loadCaseDetail() {
  initialLoading.value = true
  try {
    loadFailed.value = !(await store.openCase(route.params.caseId as string))
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  void loadCaseDetail()
})
</script>

<template>
  <div class="local-resource-case-detail">
    <AppHeader
      source="live"
      :loading="initialLoading || store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="local-resource-case-detail__main">
      <header class="local-resource-case-detail__heading">
        <span class="local-resource-case-detail__code ark-data">
          06 / CASE DETAIL
        </span>
        <h1>{{ store.caseDetail?.title ?? '成功案例' }}</h1>
        <p v-if="store.caseDetail?.summary">
          {{ store.caseDetail.summary }}
        </p>
        <span
          v-if="store.caseDetail?.is_demo"
          class="local-resource-case-detail__demo"
        >
          演示数据
        </span>
      </header>

      <div
        v-if="store.caseDetail && !loadFailed"
        class="local-resource-case-detail__sections"
      >
        <section
          class="local-resource-case-detail__section"
          data-test="case-background"
        >
          <h2>创业背景</h2>
          <p>{{ store.caseDetail.background }}</p>
        </section>

        <section
          class="local-resource-case-detail__section"
          data-test="case-journey"
        >
          <h2>创业历程</h2>
          <p>{{ store.caseDetail.journey }}</p>
        </section>

        <section
          class="local-resource-case-detail__section"
          data-test="case-lessons"
        >
          <h2>经验启示</h2>
          <p>{{ store.caseDetail.lessons }}</p>
        </section>
      </div>

      <div
        v-else-if="initialLoading"
        class="local-resource-case-detail__status"
        data-test="case-detail-loading"
        role="status"
      >
        正在加载案例详情
      </div>

      <p
        v-else
        class="local-resource-case-detail__status"
        data-test="case-detail-unavailable"
        role="alert"
      >
        案例数据暂不可用
      </p>
    </main>
  </div>
</template>

<style scoped>
.local-resource-case-detail {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.local-resource-case-detail__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.local-resource-case-detail__heading {
  padding-bottom: 28px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.local-resource-case-detail__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.local-resource-case-detail__heading h1 {
  max-width: 28ch;
  margin: 9px 0 0;
  font-size: 2.8rem;
  line-height: 1.08;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: keep-all;
}

.local-resource-case-detail__heading p {
  max-width: 68ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.local-resource-case-detail__demo {
  display: inline-block;
  margin-top: 16px;
  padding: 2px 7px;
  border: 1px solid var(--ark-signal);
  color: var(--ark-signal);
  font-size: 0.72rem;
  font-weight: 700;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.local-resource-case-detail__sections {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.local-resource-case-detail__section {
  padding: 24px 0 28px;
  border-bottom: 1px solid var(--ark-line);
}

.local-resource-case-detail__section h2 {
  margin: 0;
  font-size: 1.1rem;
}

.local-resource-case-detail__section p {
  max-width: 76ch;
  margin: 13px 0 0;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: pre-wrap;
  word-break: keep-all;
}

.local-resource-case-detail__status {
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
  .local-resource-case-detail__main {
    padding: 28px 14px 48px;
  }

  .local-resource-case-detail__heading h1 {
    font-size: 2.2rem;
  }

  .local-resource-case-detail__section {
    padding-block: 20px 24px;
  }
}
</style>
